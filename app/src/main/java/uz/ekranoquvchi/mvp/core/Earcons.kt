package uz.ekranoquvchi.mvp.core

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import uz.ekranoquvchi.mvp.diag.Diag
import uz.ekranoquvchi.mvp.diag.ErrorCode
import uz.ekranoquvchi.mvp.diag.swallowed
import uz.ekranoquvchi.mvp.util.Prefs
import java.util.Random

/**
 * Tovush signallari (8.4, 18.2): nutqsiz qisqa tovushlar. Standartda o'chiq.
 *
 * v32 gacha to'rtta ohang kod bilan hosil qilinib, har biri alohida AudioTrack bilan chalinardi. Endi tovushlar katalogi
 * (Sounds: tomchi, suv, yomg'ir, qush, bambuk va h.k.) res/raw dagi WAV fayllardan SoundPool orqali chalinadi: SoundPool
 * aynan qisqa signallar uchun yaratilgan, TalkBack ham signallarini shu bilan chaladi. Ovoz "maxsus imkoniyatlar" ovoz
 * oqimida (USAGE_ASSISTANCE_ACCESSIBILITY) chiqadi, ya'ni nutq bilan bir xil balandlik tugmasi bilan boshqariladi.
 *
 * Qaysi hodisaga qaysi tovush mosligi Sounds.resolve da (mavzu va foydalanuvchining alohida tanlovi), balandlik Prefs.earconVolume da.
 *
 * v33: ba'zi tovushlarning bir nechta varianti bor (masalan, uch xil tomchi). Har chalinganda tayyor variantlardan biri tasodifiy
 * tanlanadi, ammo avval chalingani ketma-ket ikkinchi marta chalinmaydi: tabiat tovushi bir xil takrorlanib sun'iy bo'lib qolmaydi.
 */
object Earcons {
    enum class Kind { FOCUS, EDGE, WINDOW, CLICK, SCROLL, ERROR }

    /** Bir vaqtda eshitiladigan eng ko'p tovush soni: undan ko'pi chalinsa, eng eskisi to'xtatiladi. */
    private const val MAX_STREAMS = 6

    /** Sozlamalarda "tinglab ko'rish" tovushi uchun alohida o'rin (hodisalar o'rinlari Kind.ordinal). */
    private const val PREVIEW_SLOT = 100

    /** Namuna ketma-ketligi: har bir hodisa ketma-ket eshittiriladi. */
    private const val DEMO_GAP_MS = 1100L

    /** Tabiat tovushlarida har ijroda tezlik shu miqdorgacha (foiz, ikki tomonga) o'zgaradi. */
    private const val RATE_JITTER = 0.04f

    private class Play(val slot: Int, val volume: Float, val rate: Float)

    private val NO_SAMPLES = IntArray(0)

    private val lock = Any()
    private val main = Handler(Looper.getMainLooper())
    private val demoToken = Any()
    private val random = Random()

    private var pool: SoundPool? = null

    /** Tovush id si -> variantlarning SoundPool namuna raqamlari (yuklash boshlangan; 0 bo'lsa shu variantni yuklashni boshlab bo'lmadi). */
    private val samplesOf = HashMap<String, IntArray>()

    /** Namuna raqami -> jurnal uchun nom ("drop_tiny", "drop_tiny#2" ...). */
    private val idOf = HashMap<Int, String>()

    /** Tovush id si -> oxirgi chalingan variant tartib raqami (ketma-ket ikki marta bir xil variant chalinmasligi uchun). */
    private val lastVariant = HashMap<String, Int>()

    /** Yuklanib bo'lgan namunalar; yuklanmagan namunani chalib bo'lmaydi. */
    private val ready = HashSet<Int>()
    private val failed = HashSet<Int>()

    /** Yuklanishi tugashi bilan chalinishi kerak bo'lgan (tinglab ko'rish) so'rovlar. */
    private val waiting = HashMap<Int, Play>()

    /** O'rin (slot) -> oxirgi oqim raqami: bir hodisaning yangi signali eskisini to'xtatadi. */
    private val streams = HashMap<Int, Int>()
    private val lastAt = HashMap<Kind, Long>()
    private val reported = HashSet<String>()

    /** Bir hodisaning signallari orasidagi eng kam masofa (ms): bir vaqtda kelgan takroriy hodisalar ikki marta chalinmaydi. */
    private fun minGapMs(kind: Kind): Long = when (kind) {
        Kind.FOCUS -> 20L
        Kind.CLICK -> 50L
        Kind.EDGE -> 150L
        Kind.WINDOW -> 150L
        Kind.SCROLL -> 300L
        Kind.ERROR -> 200L
    }

    /** Hodisa signalini chaladi (asosiy tugma yoqilgan bo'lsa). Hech qachon istisno tashlamaydi. */
    fun play(context: Context, kind: Kind) {
        try {
            if (!Prefs.earcons(context)) return
            val sound = Sounds.resolve(context, kind) ?: return
            val now = SystemClock.uptimeMillis()
            synchronized(lock) {
                val last = lastAt[kind]
                if (last != null && now - last < minGapMs(kind)) return
                lastAt[kind] = now
            }
            start(context, sound, kind.ordinal, false)
        } catch (ex: Throwable) {
            swallowed("Earcons.play", ex)
        }
    }

    /**
     * Joriy sozlamadagi tovushlarni oldindan yuklaydi: birinchi signal kechikmasin yoki tushib qolmasin. Xizmat ulanganda va
     * sozlama o'zgarganda chaqiriladi. Asosiy tugma o'chiq bo'lsa hech narsa yuklanmaydi.
     */
    fun prepare(context: Context) {
        try {
            if (!Prefs.earcons(context)) return
            synchronized(lock) {
                for (kind in Kind.values()) {
                    val sound = Sounds.resolve(context, kind) ?: continue
                    samplesFor(context.applicationContext, sound)
                }
            }
        } catch (ex: Throwable) {
            swallowed("Earcons.prepare", ex)
        }
    }

    /** Sozlamalarda bitta tovushni tinglab ko'rish: asosiy tugma o'chiq bo'lsa ham chalinadi. */
    fun preview(context: Context, soundId: String) {
        try {
            val sound = Sounds.byId(soundId) ?: return
            start(context, sound, PREVIEW_SLOT, true)
        } catch (ex: Throwable) {
            swallowed("Earcons.preview", ex)
        }
    }

    /** Hodisaning hozirgi tovushini tinglab ko'rish. Hodisa o'chirilgan bo'lsa false qaytaradi (hech narsa chalinmaydi). */
    fun previewKind(context: Context, kind: Kind): Boolean {
        return try {
            val sound = Sounds.resolve(context, kind) ?: return false
            start(context, sound, PREVIEW_SLOT, true)
            true
        } catch (ex: Throwable) {
            swallowed("Earcons.previewKind", ex)
            false
        }
    }

    /**
     * Hamma hodisalarning tovushlarini ketma-ket chaladi: fokus, bosish, chegara, oyna, surish, xato. themeId berilsa,
     * shu mavzuning tovushlari (foydalanuvchining alohida tanlovlarisiz) chalinadi: mavzu tanlanayotganda sinab ko'rish uchun;
     * berilmasa, hozirgi sozlamadagi tovushlar chalinadi.
     */
    fun demo(context: Context, themeId: String? = null) {
        try {
            cancelDemo()
            val app = context.applicationContext
            var at = SystemClock.uptimeMillis()
            for (kind in arrayOf(Kind.FOCUS, Kind.CLICK, Kind.EDGE, Kind.WINDOW, Kind.SCROLL, Kind.ERROR)) {
                val sound = (if (themeId == null) Sounds.resolve(app, kind) else Sounds.byId(Sounds.theme(themeId).soundId(kind))) ?: continue
                main.postAtTime({ start(app, sound, kind.ordinal, true) }, demoToken, at)
                at += DEMO_GAP_MS
            }
        } catch (ex: Throwable) {
            swallowed("Earcons.demo", ex)
        }
    }

    fun cancelDemo() {
        main.removeCallbacksAndMessages(demoToken)
    }

    /** Xizmat to'xtaganda (yoki ilova yopilganda) SoundPool bo'shatiladi; keyingi signalda qayta yaratiladi. */
    fun release() {
        cancelDemo()
        synchronized(lock) {
            try {
                pool?.release()
            } catch (ex: Throwable) {
                swallowed("Earcons.release", ex)
            }
            pool = null
            samplesOf.clear()
            idOf.clear()
            lastVariant.clear()
            ready.clear()
            failed.clear()
            waiting.clear()
            streams.clear()
        }
    }

    // ------------------------------------------------------------------ ichki ishlar

    private fun rateFor(sound: Sounds.Sound): Float =
        if (sound.nature) 1f + (random.nextFloat() * 2f - 1f) * RATE_JITTER else 1f

    /**
     * Tovushni chaladi (variantlaridan birini tanlab). U hali yuklanmagan bo'lsa: waitForLoad bo'lsa yuklanishi bilan chalinadi
     * (tinglab ko'rish), aks holda bu signal tushib qoladi (kechikib chalingan signal chalinmagani yaxshi) va yuklash boshlanadi.
     */
    private fun start(context: Context, sound: Sounds.Sound, slot: Int, waitForLoad: Boolean) {
        val volume = Prefs.earconVolume(context) / 100f
        val play = Play(slot, volume, rateFor(sound))
        var sample = 0
        var isReady = false
        synchronized(lock) {
            sample = pickSample(sound, samplesFor(context.applicationContext, sound), waitForLoad)
            if (sample == 0) return
            isReady = ready.contains(sample)
            if (!isReady && waitForLoad && !failed.contains(sample)) waiting[sample] = play
        }
        if (isReady) startSample(sample, play)
    }

    /**
     * lock bilan chaqiriladi. Yuklab bo'lingan variantlardan birini tanlaydi: tasodifiy, lekin avval chalingani emas (variant bittadan
     * ko'p bo'lsa). Hech biri tayyor bo'lmasa: waitForLoad bo'lsa birinchi yuklanayotganini qaytaradi (u tayyor bo'lgach chalinadi),
     * aks holda 0 (signal tushib qoladi).
     */
    private fun pickSample(sound: Sounds.Sound, ids: IntArray, waitForLoad: Boolean): Int {
        val usable = IntArray(ids.size)
        var count = 0
        for (i in ids.indices) {
            val id = ids[i]
            if (id != 0 && ready.contains(id)) usable[count++] = i
        }
        if (count == 0) {
            if (!waitForLoad) return 0
            for (id in ids) if (id != 0 && !failed.contains(id)) return id
            return 0
        }
        val last = lastVariant[sound.id] ?: -1
        var pick = random.nextInt(count)
        if (count > 1 && usable[pick] == last) pick = (pick + 1 + random.nextInt(count - 1)) % count
        lastVariant[sound.id] = usable[pick]
        return ids[usable[pick]]
    }

    private fun startSample(sample: Int, play: Play) {
        synchronized(lock) {
            val p = pool ?: return
            try {
                val old = streams[play.slot]
                if (old != null && old != 0) p.stop(old)
                // 0 qaytsa, oqim ochilmagan (masalan, tizim band): keyingi signal yana urinadi
                streams[play.slot] = p.play(sample, play.volume, play.volume, 1, 0, play.rate)
            } catch (ex: Throwable) {
                swallowed("Earcons.startSample", ex)
            }
        }
    }

    /**
     * lock bilan chaqiriladi. Tovushning hamma variantlari uchun namuna raqamlarini qaytaradi (yuklash kerak bo'lsa boshlaydi).
     * Hech biri yuklanmasa natija eslab qolinmaydi: keyingi signalda yana uriniladi.
     */
    private fun samplesFor(context: Context, sound: Sounds.Sound): IntArray {
        val known = samplesOf[sound.id]
        if (known != null) return known
        val p = ensurePool() ?: return NO_SAMPLES
        val ids = IntArray(sound.raws.size)
        var any = false
        for (i in sound.raws.indices) {
            val label = if (i == 0) sound.id else sound.id + "#" + (i + 1)
            val id = try {
                p.load(context, sound.raws[i], 1)
            } catch (ex: Throwable) {
                swallowed("Earcons.samplesFor", ex)
                0
            }
            if (id == 0) {
                report(label, -1)
            } else {
                idOf[id] = label
                any = true
            }
            ids[i] = id
        }
        if (any) samplesOf[sound.id] = ids
        return ids
    }

    private fun ensurePool(): SoundPool? {
        val existing = pool
        if (existing != null) return existing
        return try {
            val created = SoundPool.Builder()
                .setMaxStreams(MAX_STREAMS)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build()
                )
                .build()
            created.setOnLoadCompleteListener { _, sampleId, status -> onLoaded(sampleId, status) }
            pool = created
            created
        } catch (ex: Throwable) {
            swallowed("Earcons.ensurePool", ex)
            null
        }
    }

    private fun onLoaded(sample: Int, status: Int) {
        var name = "?"
        var pending: Play? = null
        synchronized(lock) {
            name = idOf[sample] ?: "?"
            if (status == 0) {
                ready.add(sample)
                pending = waiting.remove(sample)
            } else {
                failed.add(sample)
                waiting.remove(sample)
            }
        }
        if (status != 0) report(name, status)
        val p = pending
        if (p != null) startSample(sample, p)
    }

    /** Yuklanmagan tovush jurnalga bir marta yoziladi (qayta-qayta emas). */
    private fun report(name: String, status: Int) {
        try {
            synchronized(lock) {
                if (!reported.add(name)) return
            }
            Diag.log.log(ErrorCode.EARCON_LOAD, mapOf("sound" to name, "status" to status))
        } catch (ex: Throwable) {
            swallowed("Earcons.report", ex)
        }
    }
}
