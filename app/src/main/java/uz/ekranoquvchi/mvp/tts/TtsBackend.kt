package uz.ekranoquvchi.mvp.tts

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import uz.ekranoquvchi.mvp.diag.Diag
import uz.ekranoquvchi.mvp.diag.ErrorCode
import uz.ekranoquvchi.mvp.diag.swallowed
import uz.ekranoquvchi.mvp.util.Prefs
import java.io.File
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

internal const val SYNTH_PENDING = 0
internal const val SYNTH_DONE = 1
internal const val SYNTH_FAILED = 2
internal const val SYNTH_STOPPED = 3

/**
 * O'zbegim tizim dvigatelining "orqa qismi": haqiqiy ovozni telefondagi BOSHQA nutq dvigateli (RHVoice, Google, Samsung va h.k.)
 * beradi. O'zbegim matnni o'z qoidalari bilan tayyorlaydi, bu yerda esa tayyor matn shu dvigatelga synthesizeToFile bilan
 * beriladi va chiqqan WAV fayl PCM bo'lib tizimga qaytariladi (OzbegimTtsService).
 *
 * Bir nechta bo'lak oldindan navbatga qo'yilishi mumkin: dvigatel ularni ketma-ket tayyorlaydi, shu orada oldingisi ijro etiladi.
 * Dvigatel va til sozlamalari hamma so'rovda bir xil bo'lgani uchun faqat o'zgarganda qayta qo'llanadi.
 * Hamma holat ichida lock bilan himoyalangan; TextToSpeech asosiy oqimda yaratiladi (qaytarma chaqiruvi shu yerga keladi).
 */
internal class TtsBackend(private val context: Context) {

    class Pending(val id: String, val file: File) {
        val latch = CountDownLatch(1)

        @Volatile
        var status = SYNTH_PENDING

        @Volatile
        var errorCode = 0
    }

    private val main = Handler(Looper.getMainLooper())
    private val lock = Any()
    private val pending = ConcurrentHashMap<String, Pending>()
    private val langCache = ConcurrentHashMap<String, LangEntry>()

    /** Til tekshiruvining natijasi va vaqti: "yo'q" javobi qisqa muddat eslab qolinadi (pastga qarang: NEGATIVE_TTL_MS). */
    private class LangEntry(val status: Int, val at: Long)

    @Volatile
    private var tts: TextToSpeech? = null

    @Volatile
    private var ready = false

    @Volatile
    private var closed = false

    @Volatile
    private var readyLatch = CountDownLatch(1)

    /** Hozir ishlatilayotgan haqiqiy dvigatel (paket nomi); topilmasa null. */
    @Volatile
    var enginePackage: String? = null
        private set

    private var generation = 0
    private var counter = 0
    private var initRetries = 0
    private var appliedKey: String? = null

    /** Oxirgi qayta ulanish va oxirgi xato yozuvi vaqti (uptimeMillis): ikkalasi ham tez-tez takrorlanmasligi uchun. */
    @Volatile
    private var lastReconnectAt = 0L

    @Volatile
    private var lastFailLogAt = 0L

    /** Oxirgi submit() nima sababdan rad etilgani (FAIL_*); faqat shu zanjirda, tiklash qarori uchun. */
    @Volatile
    private var lastFail = FAIL_NONE

    private val workDir: File by lazy {
        val d = File(context.createDeviceProtectedStorageContext().cacheDir, "tts-engine")
        d.mkdirs()
        d
    }

    private val progress = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) {}

        override fun onDone(utteranceId: String?) {
            finish(utteranceId, SYNTH_DONE, 0)
        }

        @Deprecated("Deprecated in Java")
        override fun onError(utteranceId: String?) {
            finish(utteranceId, SYNTH_FAILED, -1)
        }

        override fun onError(utteranceId: String?, errorCode: Int) {
            finish(utteranceId, SYNTH_FAILED, errorCode)
        }

        override fun onStop(utteranceId: String?, interrupted: Boolean) {
            finish(utteranceId, SYNTH_STOPPED, 0)
        }
    }

    private fun finish(id: String?, status: Int, code: Int) {
        if (id == null) return
        val p = pending[id] ?: return
        if (p.status == SYNTH_PENDING) {
            p.errorCode = code
            p.status = status
        }
        p.latch.countDown()
    }

    // ------------------------------------------------------------------ ishga tushirish

    fun start() {
        cleanOld()
        if (Looper.myLooper() == Looper.getMainLooper()) create(null) else main.post { create(null) }
    }

    /** Ovoz beruvchi dvigatel tanlovi o'zgarganda dvigatelni qayta ishga tushiradi. */
    fun restart() {
        main.post {
            initRetries = 0
            create(null)
        }
    }

    private fun create(forced: String?) {
        if (closed) return
        val pkg = forced ?: EngineChoice.backendPackage(context)
        val gen = synchronized(lock) {
            generation += 1
            ready = false
            // Kutayotganlar (awaitReady) shu panjaraga bog'langan bo'lishi mumkin: hali ochilmagan bo'lsa, almashtirilmaydi
            if (readyLatch.count == 0L) readyLatch = CountDownLatch(1)
            appliedKey = null
            langCache.clear()
            generation
        }
        val old = tts
        tts = null
        try {
            old?.stop()
            old?.shutdown()
        } catch (ex: Throwable) {
            swallowed("TtsBackend.create", ex)
        }
        enginePackage = pkg
        if (pkg == null) {
            Diag.log.log(ErrorCode.TTS_INIT_FAILED, mapOf("why" to "no_backend"))
            return
        }
        val listener = TextToSpeech.OnInitListener { status -> main.post { onInit(gen, status) } }
        try {
            tts = TextToSpeech(context, listener, pkg)
        } catch (t: Throwable) {
            Diag.log.log(ErrorCode.TTS_INIT_FAILED, mapOf("exc" to t.javaClass.simpleName))
        }
    }

    private fun onInit(gen: Int, status: Int) {
        if (closed) return
        val t = tts
        val stale = synchronized(lock) { gen != generation }
        if (stale || t == null) return
        if (status != TextToSpeech.SUCCESS) {
            Diag.log.log(ErrorCode.TTS_INIT_FAILED, mapOf("status" to status, "engine" to (enginePackage ?: "?")))
            if (initRetries < 1) {
                initRetries += 1
                val alt = EngineChoice.alternative(context, enginePackage)
                if (alt != null) {
                    create(alt)
                    return
                }
            }
            // Boshqa dvigatel yo'q (yoki u ham ulanmadi): asosiy dvigatel vaqtincha band bo'lishi mumkin (masalan, RHVoice
            // ovoz paketi yuklab olinayotganda), shuning uchun bir necha marta kechikish bilan qayta ulanib ko'ramiz.
            // Ilgari bunda xizmat telefon qayta yoqilguncha jim qolardi.
            if (initRetries < MAX_INIT_RETRIES) {
                initRetries += 1
                main.postDelayed({ if (!closed) create(null) }, INIT_RETRY_DELAY_MS)
            }
            return
        }
        try {
            t.setOnUtteranceProgressListener(progress)
        } catch (ex: Throwable) {
            swallowed("TtsBackend.onInit", ex)
        }
        initRetries = 0
        val latch = synchronized(lock) {
            ready = true
            readyLatch
        }
        latch.countDown()
    }

    /** Dvigatel tayyor bo'lguncha kutadi (so'rov oqimida chaqiriladi, asosiy oqimda emas). */
    fun awaitReady(timeoutMs: Long): Boolean {
        if (closed) return false
        if (ready) return true
        val latch = readyLatch
        try {
            latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        } catch (_: InterruptedException) {
            return false
        }
        return ready && !closed
    }

    // ------------------------------------------------------------------ tillar

    /** Orqa dvigatel tilni qo'llab-quvvatlashi: TextToSpeech.LANG_* kodlari. Natija keshlanadi. */
    fun languageStatus(locale: Locale): Int {
        val key = locale.toLanguageTag()
        val now = SystemClock.uptimeMillis()
        val cached = langCache[key]
        // "Bor" javobi eslab qolinadi; "yo'q" javobi faqat qisqa muddat: ilgari u dvigatel qayta ishga tushguncha qolib ketardi,
        // shuning uchun RHVoice'da ruscha ovoz paketi yuklab olingandan keyin ham til "yo'q" deb javob berilardi
        if (cached != null && (cached.status >= TextToSpeech.LANG_AVAILABLE || now - cached.at < NEGATIVE_TTL_MS)) return cached.status
        val t = tts ?: return TextToSpeech.LANG_NOT_SUPPORTED
        val r = try {
            t.isLanguageAvailable(locale)
        } catch (_: Throwable) {
            TextToSpeech.LANG_NOT_SUPPORTED
        }
        langCache[key] = LangEntry(r, now)
        return r
    }

    fun availableLocales(): Set<Locale> = try {
        tts?.availableLanguages ?: emptySet()
    } catch (_: Throwable) {
        emptySet()
    }

    // ------------------------------------------------------------------ sintez

    /**
     * Matn bo'lagini orqa dvigatelga navbatga qo'yadi. Natija WAV fayl bo'lib keladi (await, readPcm).
     * Til yoki ovoz qo'llanmasa yoki dvigatel rad etsa null. Dvigatel bilan aloqa uzilgan bo'lsa (masalan, RHVoice ovoz paketi
     * yuklab olinganda jarayoni qayta ishga tushadi, TextToSpeech esa o'zi qayta ulanmaydi va har so'rovga xato qaytaradi),
     * qayta ulanib, bo'lakni bir marta qayta urinib ko'radi.
     */
    fun submit(text: String, locale: Locale, rate: Int, pitch: Int): Pending? {
        val t = tts ?: return null
        val first = synchronized(lock) { submitLocked(t, text, locale, rate, pitch) }
        if (first != null) return first
        val why = lastFail
        val dead = why == FAIL_BOUND || (why == FAIL_LANG && looksDisconnected(t))
        if (!dead) {
            if (why == FAIL_LANG) noteFailure("lang_unsupported", locale, 0)
            return null
        }
        if (!reconnect()) {
            noteFailure("reconnect_failed", locale, why)
            return null
        }
        val t2 = tts ?: return null
        val second = synchronized(lock) { submitLocked(t2, text, locale, rate, pitch) }
        if (second == null) noteFailure("after_reconnect", locale, lastFail)
        return second
    }

    private fun submitLocked(t: TextToSpeech, text: String, locale: Locale, rate: Int, pitch: Int): Pending? {
        lastFail = FAIL_NONE
        if (!ready || closed) {
            lastFail = FAIL_NOT_READY
            return null
        }
        counter += 1
        val id = "z" + counter
        val file = File(workDir, id + "-" + SystemClock.uptimeMillis() + ".wav")
        val p = Pending(id, file)
        pending[id] = p
        try {
            if (!applyLanguage(t, locale)) {
                pending.remove(id)
                lastFail = FAIL_LANG
                return null
            }
            t.setSpeechRate(rate / 100f)
            t.setPitch(pitch / 100f)
            val r = t.synthesizeToFile(text, Bundle(), file, id)
            if (r != TextToSpeech.SUCCESS) {
                pending.remove(id)
                lastFail = FAIL_BOUND
                return null
            }
        } catch (_: Throwable) {
            pending.remove(id)
            lastFail = FAIL_EXCEPTION
            return null
        }
        return p
    }

    /**
     * So'ralgan tilni va shu til uchun tanlangan ovozni qo'llaydi. Ilgari ovoz faqat o'zbek tilida qo'llanardi: ruscha ovoz
     * (masalan, RHVoice'dagi) tanlansa ham hisobga olinmasdi va dvigatelning standart ovozi gapirardi. Endi har til uchun
     * Ovozlar ekranida tanlangan ovoz (Prefs.voiceFor) qo'llanadi. So'ralgan til dvigatelda umuman bo'lmasa, foydalanuvchi
     * tanlagan boshqa tildagi ovoz (agar bu dvigatelda bo'lsa) ishlatiladi: telefon jim qolmasligi kerak.
     */
    private fun applyLanguage(t: TextToSpeech, locale: Locale): Boolean {
        val lang = locale.language
        var voice = Prefs.voiceFor(context, lang)
        // Til alohida saqlanmagan eski tanlov: o'zbekchada ilgari ham shu qo'llanardi (ovozning tili tekshiriladi)
        if (voice.isEmpty() && Prefs.langKey(lang) == "uz") voice = Prefs.voice(context)
        val key = locale.toLanguageTag() + "|" + voice
        if (key == appliedKey) return true
        val r = t.setLanguage(locale)
        if (r < TextToSpeech.LANG_AVAILABLE) {
            val chosen = Prefs.voice(context)
            if (chosen.isNotEmpty() && applyVoice(t, chosen, null)) {
                appliedKey = key
                return true
            }
            return false
        }
        if (voice.isNotEmpty()) applyVoice(t, voice, lang)
        appliedKey = key
        return true
    }

    /**
     * Nomi bo'yicha ovozni qo'yadi. lang berilsa, ovozning tili ham mos kelishi kerak (ruscha so'rovga o'zbekcha ovoz qo'yilmasin);
     * null bo'lsa, til tekshirilmaydi. Dvigatellar ovoz tilini "uz" yoki "uzb" deb beradi: Prefs.langKey ikkalasini tenglashtiradi.
     */
    private fun applyVoice(t: TextToSpeech, saved: String, lang: String?): Boolean {
        try {
            val voices = t.voices ?: return false
            val want = if (lang == null) null else Prefs.langKey(lang)
            for (v in voices) {
                if (v.name != saved) continue
                if (want != null && Prefs.langKey(v.locale.language) != want) continue
                return t.setVoice(v) == TextToSpeech.SUCCESS
            }
        } catch (ex: Throwable) {
            swallowed("TtsBackend.applyVoice", ex)
        }
        return false
    }

    // ------------------------------------------------------------------ aloqa uzilsa tiklash

    /**
     * Orqa dvigatel bilan aloqa uzilganga o'xshaydimi: til ro'yxati bo'sh yoki yo'q. Ishlab turgan dvigatel hech bo'lmasa
     * bitta til beradi; bog'lanmagan TextToSpeech esa null qaytaradi.
     */
    private fun looksDisconnected(t: TextToSpeech): Boolean = try {
        t.availableLanguages.isNullOrEmpty()
    } catch (_: Throwable) {
        true
    }

    /**
     * Orqa dvigatelni qayta ulaydi va tayyor bo'lguncha kutadi (so'rov oqimida chaqiriladi, asosiy oqimda emas). Takroriy
     * qayta ulanishlar RECONNECT_GAP_MS dan tez emas: hozirgi qayta ulanish davom etayotgan bo'lsa, shuni kutadi.
     */
    private fun reconnect(): Boolean {
        val now = SystemClock.uptimeMillis()
        var start = false
        synchronized(lock) {
            if (closed) return false
            if (ready) {
                if (now - lastReconnectAt < RECONNECT_GAP_MS) return false
                lastReconnectAt = now
                ready = false
                if (readyLatch.count == 0L) readyLatch = CountDownLatch(1)
                start = true
            }
        }
        if (start) {
            Diag.log.log(ErrorCode.TTS_ENGINE_SWITCHED, mapOf("step" to "backend_reconnect", "engine" to (enginePackage ?: "?")))
            main.post {
                initRetries = 0
                create(null)
            }
        }
        return awaitReady(RECONNECT_WAIT_MS)
    }

    /** Sintez xatosi (callback orqali): dvigatel xizmati xato bersa, keyingi so'rov oldidan qayta ulanish rejalashtiriladi. */
    fun onSynthError(locale: Locale, code: Int) {
        noteFailure("synth", locale, code)
        if (code != TextToSpeech.ERROR_SERVICE && code != TextToSpeech.ERROR_NOT_INSTALLED_YET) return
        val now = SystemClock.uptimeMillis()
        val go = synchronized(lock) {
            if (closed || now - lastReconnectAt < RECONNECT_GAP_MS) {
                false
            } else {
                lastReconnectAt = now
                true
            }
        }
        if (go) {
            main.post {
                initRetries = 0
                create(null)
            }
        }
    }

    /**
     * Xatoni jurnalga yozadi (matnsiz): bosqich, til, kod, dvigatel va u bergan tillar ro'yxati. Oldin faqat "chunks_failed"
     * deb yozilardi va nima sababdan ekani ma'lum emasdi. Takrorlanuvchi xato jurnalni to'ldirmasligi uchun 5 soniyada bir marta.
     */
    fun noteFailure(stage: String, locale: Locale?, code: Int) {
        val now = SystemClock.uptimeMillis()
        if (now - lastFailLogAt < FAIL_LOG_GAP_MS) return
        lastFailLogAt = now
        try {
            val langs = availableLocales().joinToString(",") { it.toLanguageTag() }.take(120)
            Diag.log.log(
                ErrorCode.TTS_SERVICE_ERROR,
                mapOf(
                    "why" to ("backend_" + stage),
                    "lang" to (locale?.toLanguageTag() ?: ""),
                    "code" to code,
                    "engine" to (enginePackage ?: "?"),
                    "langs" to langs,
                ),
            )
        } catch (ex: Throwable) {
            swallowed("TtsBackend.noteFailure", ex)
        }
    }

    /** Bo'lak tayyor bo'lguncha kutadi. SYNTH_PENDING qaytsa, vaqt tugagan. */
    fun await(p: Pending, timeoutMs: Long): Int {
        val ok = try {
            p.latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        } catch (_: InterruptedException) {
            false
        }
        return if (ok) p.status else SYNTH_PENDING
    }

    /** Tayyor WAV'ni o'qiydi va faylni o'chiradi. */
    fun readPcm(p: Pending): Pcm? {
        val pcm = WavReader.read(p.file)
        discard(p)
        return pcm
    }

    fun discard(p: Pending) {
        pending.remove(p.id)
        try {
            p.file.delete()
        } catch (ex: Throwable) {
            swallowed("TtsBackend.discard", ex)
        }
    }

    /** Hamma kutilayotgan bo'laklarni to'xtatadi (mijoz to'xtatganda yoki vaqt tugaganda). */
    fun stopAll() {
        try {
            tts?.stop()
        } catch (ex: Throwable) {
            swallowed("TtsBackend.stopAll", ex)
        }
        for (p in pending.values) {
            if (p.status == SYNTH_PENDING) p.status = SYNTH_STOPPED
            p.latch.countDown()
        }
    }

    fun shutdown() {
        closed = true
        main.removeCallbacksAndMessages(null)
        val t = tts
        tts = null
        ready = false
        try {
            t?.stop()
            t?.shutdown()
        } catch (ex: Throwable) {
            swallowed("TtsBackend.shutdown", ex)
        }
        for (p in pending.values) {
            p.status = SYNTH_STOPPED
            p.latch.countDown()
            try {
                p.file.delete()
            } catch (ex: Throwable) {
                swallowed("TtsBackend.shutdown", ex)
            }
        }
        pending.clear()
        readyLatch.countDown()
    }

    /** Oldingi ishdan qolgan eskirgan vaqtinchalik fayllarni o'chiradi. */
    private fun cleanOld() {
        try {
            val now = System.currentTimeMillis()
            val files = workDir.listFiles() ?: return
            for (f in files) if (now - f.lastModified() > 600_000L) f.delete()
        } catch (ex: Throwable) {
            swallowed("TtsBackend.cleanOld", ex)
        }
    }

    private companion object {
        /** "Til yo'q" javobi shuncha vaqt eslab qolinadi (ms): yangi ovoz paketi yuklab olinsa, tez ko'rinsin. */
        const val NEGATIVE_TTL_MS = 4000L

        /** Qayta ulanishlar orasidagi eng kam vaqt va kutish chegarasi (ms). */
        const val RECONNECT_GAP_MS = 5000L
        const val RECONNECT_WAIT_MS = 4000L

        /** Ulanish (init) xatosidan keyin qayta urinishlar soni va ular orasidagi kutish (ms). */
        const val MAX_INIT_RETRIES = 4
        const val INIT_RETRY_DELAY_MS = 3000L

        /** Bir xil xato yozuvlari orasidagi eng kam vaqt (ms). */
        const val FAIL_LOG_GAP_MS = 5000L

        const val FAIL_NONE = 0
        const val FAIL_NOT_READY = 1
        const val FAIL_LANG = 2
        const val FAIL_BOUND = 3
        const val FAIL_EXCEPTION = 4
    }
}
