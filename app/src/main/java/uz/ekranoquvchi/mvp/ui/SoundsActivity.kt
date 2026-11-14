package uz.ekranoquvchi.mvp.ui

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SeekBarPreference
import uz.ekranoquvchi.mvp.R
import uz.ekranoquvchi.mvp.core.Earcons
import uz.ekranoquvchi.mvp.core.Sounds
import uz.ekranoquvchi.mvp.util.Prefs
import uz.ekranoquvchi.mvp.util.SystemUtil

/**
 * Sozlamalar > Tovush signallari (v32, v33): tovushlar mavzusi (iPhone uslubi, qadamlar, suv, yomg'ir, o'rmon, sokinlik, aralash), signallar balandligi,
 * har bir hodisa (fokus, bosish, chegara, oyna, surish, xato) uchun alohida tovush yoki o'chirish, hamma tovushni
 * birma-bir tinglab ko'rish va boshqa ekran o'quvchi (TalkBack) yoqiq bo'lganda ham signal chalish tugmasi.
 */
class SoundsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = getString(R.string.snd_title)
        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction()
                .replace(android.R.id.content, SoundsFragment())
                .commit()
        }
    }
}

class SoundsFragment : PreferenceFragmentCompat() {
    private val main = Handler(Looper.getMainLooper())
    private val eventPrefs = LinkedHashMap<Earcons.Kind, ListPreference>()

    /** Surgich siljiganda har bir qadamda emas, to'xtagach bir marta eshittiriladi. */
    private val volumeTest = Runnable { context?.let { previewAny(it) } }
    private val statusRefresh = Runnable { refreshStandbyStatus() }

    override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
        val ctx = requireContext()
        // Sozlamalar xizmat bilan bir xil (qurilma-himoyalangan) faylga yoziladi
        preferenceManager.preferenceDataStore = SharedPrefsStore(ctx.applicationContext, Prefs.get(ctx))
        setPreferencesFromResource(R.xml.preferences_sounds, rootKey)
        bindMain(ctx)
        bindStandby()
        buildEvents(ctx)
        buildCatalog(ctx)
        refreshStandbyStatus()
    }

    override fun onResume() {
        super.onResume()
        // Maxsus imkoniyatlardan qaytilganda xizmat holati o'zgargan bo'lishi mumkin
        refreshStandbyStatus()
    }

    override fun onStop() {
        Earcons.cancelDemo()
        main.removeCallbacks(volumeTest)
        super.onStop()
    }

    override fun onDestroyView() {
        main.removeCallbacks(statusRefresh)
        super.onDestroyView()
    }

    // ------------------------------------------------------------------ asosiy: mavzu, balandlik, sinab ko'rish

    private fun bindMain(ctx: Context) {
        findPreference<ListPreference>(Prefs.EARCON_THEME)?.let { list ->
            list.entries = Sounds.THEMES.map { getString(it.nameRes) }.toTypedArray()
            list.entryValues = Sounds.THEMES.map { it.id }.toTypedArray()
            list.dialogTitle = getString(R.string.snd_theme)
            list.setOnPreferenceChangeListener { _, newValue ->
                val theme = newValue as? String ?: return@setOnPreferenceChangeListener true
                refreshEventSummaries(theme)
                // Yangi mavzuning hamma tovushi ketma-ket eshittiriladi (tanlov hali saqlanmagan, shuning uchun mavzu nomi beriladi)
                Earcons.demo(ctx, theme)
                true
            }
        }
        findPreference<SeekBarPreference>(Prefs.EARCON_VOLUME)?.setOnPreferenceChangeListener { _, _ ->
            main.removeCallbacks(volumeTest)
            main.postDelayed(volumeTest, VOLUME_TEST_DELAY_MS)
            true
        }
        // Surgich ekran o'quvchi bilan qiyin bo'lishi mumkin: aniq son yozish oynasi ham bor (nutq tezligidagi kabi)
        findPreference<Preference>("earcon_volume_exact")?.let { p ->
            p.setOnPreferenceClickListener {
                NumberDialog.show(
                    requireContext(), R.string.snd_volume, Prefs.EARCON_VOLUME, Prefs.EARCON_VOLUME_RANGE, 60,
                    onTest = { previewAny(requireContext()) },
                    testOnChange = true
                ) {
                    refreshVolume()
                }
                true
            }
        }
        findPreference<Preference>("earcon_demo")?.setOnPreferenceClickListener {
            Earcons.demo(requireContext())
            true
        }
        refreshVolume()
    }

    private fun refreshVolume() {
        val v = Prefs.earconVolume(requireContext())
        findPreference<SeekBarPreference>(Prefs.EARCON_VOLUME)?.value = v
        findPreference<Preference>("earcon_volume_exact")?.summary = getString(R.string.snd_volume_exact_summary, v)
    }

    /** Balandlikni sinash: bosish tovushi (o'chiq bo'lsa, fokus tovushi) chalinadi. */
    private fun previewAny(ctx: Context) {
        if (!Earcons.previewKind(ctx, Earcons.Kind.CLICK)) Earcons.previewKind(ctx, Earcons.Kind.FOCUS)
    }

    // ------------------------------------------------------------------ boshqa ekran o'quvchi bilan (afzal ko'rilgan mexanizm)

    private fun bindStandby() {
        val change = Preference.OnPreferenceChangeListener { _, _ ->
            // Qiymat saqlangandan keyin holat matni yangilanadi
            main.removeCallbacks(statusRefresh)
            main.postDelayed(statusRefresh, 200L)
            true
        }
        findPreference<Preference>(Prefs.EARCONS)?.onPreferenceChangeListener = change
        findPreference<Preference>(Prefs.EARCONS_STANDBY)?.onPreferenceChangeListener = change
    }

    /** Holat matni: nima yoqilmagani va nima kerakligi aytiladi (ekran o'quvchi foydalanuvchisi uchun muhim). */
    private fun refreshStandbyStatus() {
        val ctx = context ?: return
        val text = when {
            !Prefs.earcons(ctx) -> getString(R.string.snd_status_master_off)
            !Prefs.earconsStandby(ctx) -> getString(R.string.snd_status_off)
            !SystemUtil.isServiceEnabled(ctx) -> getString(R.string.snd_status_no_service)
            else -> getString(R.string.snd_status_ready)
        }
        findPreference<Preference>("earcons_standby_status")?.summary = text
    }

    // ------------------------------------------------------------------ har bir hodisa uchun tovush

    private fun buildEvents(ctx: Context) {
        val category = findPreference<PreferenceCategory>("snd_events") ?: return
        val entries = ArrayList<String>()
        val values = ArrayList<String>()
        entries.add(getString(R.string.snd_choice_theme_entry))
        values.add(Sounds.OVERRIDE_THEME)
        entries.add(getString(R.string.snd_choice_off))
        values.add(Sounds.OVERRIDE_OFF)
        for (s in Sounds.ALL) {
            entries.add(getString(s.nameRes))
            values.add(s.id)
        }
        eventPrefs.clear()
        for (kind in Earcons.Kind.values()) {
            // Dasturda yaratiladigan sozlamalar menejerning mavzuli konteksti bilan yaratiladi (ko'rinishi XML dagilar bilan bir xil bo'lishi uchun)
            val list = ListPreference(preferenceManager.context)
            list.key = Prefs.earconKey(kind)
            list.title = getString(Sounds.eventTitleRes(kind))
            list.dialogTitle = list.title
            list.entries = entries.toTypedArray()
            list.entryValues = values.toTypedArray()
            list.setDefaultValue(Sounds.OVERRIDE_THEME)
            list.setOnPreferenceChangeListener { _, newValue ->
                val value = newValue as? String ?: return@setOnPreferenceChangeListener true
                list.summary = choiceSummary(kind, value, Prefs.earconTheme(ctx))
                // Tanlangan tovush darhol eshittiriladi (o'chirilgan bo'lsa, hech narsa chalinmaydi)
                val id = soundIdFor(kind, value, Prefs.earconTheme(ctx))
                if (id != null) Earcons.preview(ctx, id)
                true
            }
            category.addPreference(list)
            eventPrefs[kind] = list
        }
        refreshEventSummaries(Prefs.earconTheme(ctx))
    }

    private fun refreshEventSummaries(theme: String) {
        // Fragment ekrandan olingan bo'lsa (getString ishlamaydi), hech narsa qilinmaydi
        if (context == null) return
        for ((kind, list) in eventPrefs) {
            list.summary = choiceSummary(kind, list.value ?: Sounds.OVERRIDE_THEME, theme)
        }
    }

    /** Hodisaga tanlangan qiymat bo'yicha ijro etiladigan tovush id si (null: o'chiq). */
    private fun soundIdFor(kind: Earcons.Kind, value: String, theme: String): String? = when {
        value == Sounds.OVERRIDE_OFF -> null
        value == Sounds.OVERRIDE_THEME || Sounds.byId(value) == null -> Sounds.theme(theme).soundId(kind)
        else -> value
    }

    private fun choiceSummary(kind: Earcons.Kind, value: String, theme: String): String {
        if (value == Sounds.OVERRIDE_OFF) return getString(R.string.snd_choice_off)
        val id = soundIdFor(kind, value, theme)
        val name = Sounds.byId(id)?.let { getString(it.nameRes) } ?: ""
        return if (value == Sounds.OVERRIDE_THEME || Sounds.byId(value) == null) getString(R.string.snd_choice_theme, name) else name
    }

    // ------------------------------------------------------------------ tinglab ko'rish: hamma tovush

    private fun buildCatalog(ctx: Context) {
        val screen = preferenceScreen ?: return
        for (group in Sounds.Group.values()) {
            val category = PreferenceCategory(preferenceManager.context)
            category.title = getString(group.titleRes)
            screen.addPreference(category)
            for (sound in Sounds.ALL) {
                if (sound.group != group) continue
                val row = Preference(preferenceManager.context)
                row.title = getString(sound.nameRes)
                row.isPersistent = false
                row.setOnPreferenceClickListener {
                    Earcons.preview(ctx, sound.id)
                    true
                }
                category.addPreference(row)
            }
        }
    }

    private companion object {
        const val VOLUME_TEST_DELAY_MS = 350L
    }
}
