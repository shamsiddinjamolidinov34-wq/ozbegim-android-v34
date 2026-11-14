package uz.ekranoquvchi.mvp.core

import android.content.Context
import uz.ekranoquvchi.mvp.R
import uz.ekranoquvchi.mvp.util.Prefs

/**
 * Tovush signallari katalogi (v33). Har bir tovush res/raw dagi bitta yoki bir nechta (variant) WAV fayl: ularning hammasi
 * tools/make_sounds.py skripti bilan matematik usulda yaratilgan (tashqi yozuv ishlatilmagan, shuning uchun mualliflik huquqi
 * muammosi yo'q). "iPhone uslubidagi" tovushlar Apple yozuvlari emas, ularning xarakteriga ("tik", "tok", "pop") yangidan sintez
 * qilingan asl tovushlar.
 *
 * "Mavzu" har bir hodisa (fokus, bosish, chegara, oyna, surish, xato) uchun tayyor tovushlar to'plami. Foydalanuvchi
 * istasa, har bir hodisaga katalogdan alohida tovush tanlaydi yoki uni o'chiradi (Prefs.earconOverride).
 */
object Sounds {
    /** Tovushlar guruhi: sozlamalardagi "Tinglab ko'rish" ro'yxatida sarlavha bo'ladi (ALL ro'yxatida shu tartibda joylashgan). */
    enum class Group(val titleRes: Int) {
        TONE(R.string.snd_group_tone),
        IOS(R.string.snd_group_ios),
        WATER(R.string.snd_group_water),
        RAIN(R.string.snd_group_rain),
        NATURE(R.string.snd_group_nature),
        STEP(R.string.snd_group_step),
        ZEN(R.string.snd_group_zen),
    }

    /**
     * @param id kalit (saqlanadigan qiymat; res/raw/snd_<id>.wav fayl nomi bilan bir xil)
     * @param raws variantlar: birinchisi snd_<id>.wav, keyingilari snd_<id>_2.wav, snd_<id>_3.wav ... Ular navbat bilan chalinadi
     *  (bir variant ketma-ket ikki marta chalinmaydi), shunda tabiat tovushi takrorlanib "mashinadek" bo'lib qolmaydi
     * @param nature true bo'lsa har ijroda tezlik biroz o'zgartiriladi (tabiatda ikki tovush bir xil emas, takrorlanish zerikarli bo'lmaydi)
     */
    class Sound(val id: String, val raws: IntArray, val nameRes: Int, val group: Group, val nature: Boolean)

    private fun snd(id: String, group: Group, nature: Boolean, nameRes: Int, vararg raws: Int) = Sound(id, raws, nameRes, group, nature)

    /**
     * Aks sadoli (reverb) tovushlar uchta: "Chuqur tomchi", "G'orda tomchi" va "Shamol qo'ng'irog'i" (nomlarida shunday yozilgan).
     * Qolgan hammasi quruq: ularning uzunligi aks sadodan emas, narsaning o'z so'nishidan.
     * Ohangli tovushlar (iPhone uslubi, kalimba, qo'ng'iroq, kosa): balandligi o'zgarsa kuy buziladi, shuning uchun nature = false.
     */
    val ALL: List<Sound> = listOf(
        snd("tone_tik", Group.TONE, false, R.string.snd_name_tone_tik, R.raw.snd_tone_tik),
        snd("tone_tuk", Group.TONE, false, R.string.snd_name_tone_tuk, R.raw.snd_tone_tuk),
        snd("tone_edge", Group.TONE, false, R.string.snd_name_tone_edge, R.raw.snd_tone_edge),
        snd("tone_window", Group.TONE, false, R.string.snd_name_tone_window, R.raw.snd_tone_window),
        snd("tone_scroll", Group.TONE, false, R.string.snd_name_tone_scroll, R.raw.snd_tone_scroll),
        snd("tone_error", Group.TONE, false, R.string.snd_name_tone_error, R.raw.snd_tone_error),

        snd("ios_tick", Group.IOS, false, R.string.snd_name_ios_tick, R.raw.snd_ios_tick),
        snd("ios_tock", Group.IOS, false, R.string.snd_name_ios_tock, R.raw.snd_ios_tock),
        snd("ios_pop", Group.IOS, false, R.string.snd_name_ios_pop, R.raw.snd_ios_pop),
        snd("ios_thud", Group.IOS, false, R.string.snd_name_ios_thud, R.raw.snd_ios_thud),
        snd("ios_swoosh", Group.IOS, false, R.string.snd_name_ios_swoosh, R.raw.snd_ios_swoosh),
        snd("ios_scroll", Group.IOS, false, R.string.snd_name_ios_scroll, R.raw.snd_ios_scroll),
        snd("ios_error", Group.IOS, false, R.string.snd_name_ios_error, R.raw.snd_ios_error),
        snd("ios_glass", Group.IOS, false, R.string.snd_name_ios_glass, R.raw.snd_ios_glass),
        snd("ios_marimba", Group.IOS, false, R.string.snd_name_ios_marimba, R.raw.snd_ios_marimba),
        snd("ios_chime_up", Group.IOS, false, R.string.snd_name_ios_chime_up, R.raw.snd_ios_chime_up),

        snd("drop_tiny", Group.WATER, true, R.string.snd_name_drop_tiny, R.raw.snd_drop_tiny, R.raw.snd_drop_tiny_2, R.raw.snd_drop_tiny_3, R.raw.snd_drop_tiny_4),
        snd("drop_water", Group.WATER, true, R.string.snd_name_drop_water, R.raw.snd_drop_water, R.raw.snd_drop_water_2, R.raw.snd_drop_water_3),
        snd("drop_big", Group.WATER, true, R.string.snd_name_drop_big, R.raw.snd_drop_big, R.raw.snd_drop_big_2, R.raw.snd_drop_big_3),
        snd("drop_stone", Group.WATER, true, R.string.snd_name_drop_stone, R.raw.snd_drop_stone, R.raw.snd_drop_stone_2, R.raw.snd_drop_stone_3),
        snd("drop_pair", Group.WATER, true, R.string.snd_name_drop_pair, R.raw.snd_drop_pair, R.raw.snd_drop_pair_2),
        snd("drop_deep", Group.WATER, true, R.string.snd_name_drop_deep, R.raw.snd_drop_deep),
        snd("drop_cave", Group.WATER, true, R.string.snd_name_drop_cave, R.raw.snd_drop_cave),
        snd("water_splash", Group.WATER, true, R.string.snd_name_water_splash, R.raw.snd_water_splash, R.raw.snd_water_splash_2),
        snd("water_ripple", Group.WATER, true, R.string.snd_name_water_ripple, R.raw.snd_water_ripple, R.raw.snd_water_ripple_2),
        snd("water_brook", Group.WATER, true, R.string.snd_name_water_brook, R.raw.snd_water_brook),
        snd("water_wave", Group.WATER, true, R.string.snd_name_water_wave, R.raw.snd_water_wave),
        snd("water_fountain", Group.WATER, true, R.string.snd_name_water_fountain, R.raw.snd_water_fountain),

        snd("rain_tap", Group.RAIN, true, R.string.snd_name_rain_tap, R.raw.snd_rain_tap, R.raw.snd_rain_tap_2, R.raw.snd_rain_tap_3, R.raw.snd_rain_tap_4),
        snd("rain_leaves", Group.RAIN, true, R.string.snd_name_rain_leaves, R.raw.snd_rain_leaves, R.raw.snd_rain_leaves_2, R.raw.snd_rain_leaves_3),
        snd("rain_puddle", Group.RAIN, true, R.string.snd_name_rain_puddle, R.raw.snd_rain_puddle, R.raw.snd_rain_puddle_2, R.raw.snd_rain_puddle_3),
        snd("rain_shower", Group.RAIN, true, R.string.snd_name_rain_shower, R.raw.snd_rain_shower),
        snd("rain_roof", Group.RAIN, true, R.string.snd_name_rain_roof, R.raw.snd_rain_roof),

        snd("bird_tweet", Group.NATURE, true, R.string.snd_name_bird_tweet, R.raw.snd_bird_tweet, R.raw.snd_bird_tweet_2, R.raw.snd_bird_tweet_3),
        snd("bird_trill", Group.NATURE, true, R.string.snd_name_bird_trill, R.raw.snd_bird_trill, R.raw.snd_bird_trill_2),
        snd("bird_dove", Group.NATURE, true, R.string.snd_name_bird_dove, R.raw.snd_bird_dove),
        snd("bird_sparrow", Group.NATURE, true, R.string.snd_name_bird_sparrow, R.raw.snd_bird_sparrow, R.raw.snd_bird_sparrow_2, R.raw.snd_bird_sparrow_3),
        snd("bird_bulbul", Group.NATURE, true, R.string.snd_name_bird_bulbul, R.raw.snd_bird_bulbul),
        snd("bird_hoopoe", Group.NATURE, true, R.string.snd_name_bird_hoopoe, R.raw.snd_bird_hoopoe),
        snd("cricket", Group.NATURE, true, R.string.snd_name_cricket, R.raw.snd_cricket, R.raw.snd_cricket_2),
        snd("leaf_rustle", Group.NATURE, true, R.string.snd_name_leaf_rustle, R.raw.snd_leaf_rustle, R.raw.snd_leaf_rustle_2, R.raw.snd_leaf_rustle_3),
        snd("wind_breeze", Group.NATURE, true, R.string.snd_name_wind_breeze, R.raw.snd_wind_breeze),
        snd("fire_crackle", Group.NATURE, true, R.string.snd_name_fire_crackle, R.raw.snd_fire_crackle),

        snd("step_grass", Group.STEP, true, R.string.snd_name_step_grass, R.raw.snd_step_grass, R.raw.snd_step_grass_2, R.raw.snd_step_grass_3, R.raw.snd_step_grass_4),
        snd("step_gravel", Group.STEP, true, R.string.snd_name_step_gravel, R.raw.snd_step_gravel, R.raw.snd_step_gravel_2, R.raw.snd_step_gravel_3),
        snd("step_wood", Group.STEP, true, R.string.snd_name_step_wood, R.raw.snd_step_wood, R.raw.snd_step_wood_2, R.raw.snd_step_wood_3),
        snd("step_snow", Group.STEP, true, R.string.snd_name_step_snow, R.raw.snd_step_snow, R.raw.snd_step_snow_2, R.raw.snd_step_snow_3),

        snd("bamboo_tap", Group.ZEN, true, R.string.snd_name_bamboo_tap, R.raw.snd_bamboo_tap, R.raw.snd_bamboo_tap_2, R.raw.snd_bamboo_tap_3),
        snd("wood_block", Group.ZEN, true, R.string.snd_name_wood_block, R.raw.snd_wood_block, R.raw.snd_wood_block_2, R.raw.snd_wood_block_3, R.raw.snd_wood_block_4),
        snd("pebble", Group.ZEN, true, R.string.snd_name_pebble, R.raw.snd_pebble, R.raw.snd_pebble_2, R.raw.snd_pebble_3, R.raw.snd_pebble_4),
        snd("kalimba", Group.ZEN, false, R.string.snd_name_kalimba, R.raw.snd_kalimba, R.raw.snd_kalimba_2, R.raw.snd_kalimba_3),
        snd("chime_wind", Group.ZEN, false, R.string.snd_name_chime_wind, R.raw.snd_chime_wind),
        snd("bowl_soft", Group.ZEN, false, R.string.snd_name_bowl_soft, R.raw.snd_bowl_soft),
    )

    private val BY_ID: Map<String, Sound> = ALL.associateBy { it.id }

    fun byId(id: String?): Sound? = if (id == null) null else BY_ID[id]

    // ------------------------------------------------------------------ mavzular

    /** Mavzu: har bir hodisa uchun bitta tovush (id lar ALL ro'yxatidagi bilan bir xil). */
    class Theme(
        val id: String,
        val nameRes: Int,
        val focus: String,
        val click: String,
        val edge: String,
        val window: String,
        val scroll: String,
        val error: String,
    ) {
        fun soundId(kind: Earcons.Kind): String = when (kind) {
            Earcons.Kind.FOCUS -> focus
            Earcons.Kind.CLICK -> click
            Earcons.Kind.EDGE -> edge
            Earcons.Kind.WINDOW -> window
            Earcons.Kind.SCROLL -> scroll
            Earcons.Kind.ERROR -> error
        }
    }

    /** Standart mavzu v31 dagi to'rtta ohangni aynan saqlaydi (fokus, bosish, chegara, oyna), shuning uchun yangilanishda hech narsa o'zgarmaydi. */
    const val DEFAULT_THEME = "classic"

    val THEMES: List<Theme> = listOf(
        Theme("classic", R.string.snd_theme_classic, "tone_tik", "tone_tuk", "tone_edge", "tone_window", "tone_scroll", "tone_error"),
        Theme("ios", R.string.snd_theme_ios, "ios_tick", "ios_pop", "ios_thud", "ios_swoosh", "ios_scroll", "ios_error"),
        Theme("steps", R.string.snd_theme_steps, "step_grass", "wood_block", "step_wood", "bird_sparrow", "step_gravel", "drop_deep"),
        Theme("water", R.string.snd_theme_water, "drop_tiny", "drop_water", "water_ripple", "water_wave", "drop_pair", "drop_deep"),
        Theme("rain", R.string.snd_theme_rain, "rain_tap", "rain_leaves", "wind_breeze", "rain_shower", "leaf_rustle", "drop_deep"),
        Theme("forest", R.string.snd_theme_forest, "wood_block", "bird_tweet", "bird_dove", "bird_trill", "cricket", "bamboo_tap"),
        Theme("zen", R.string.snd_theme_zen, "pebble", "bamboo_tap", "bowl_soft", "chime_wind", "wood_block", "drop_deep"),
        Theme("mix", R.string.snd_theme_mix, "drop_tiny", "bamboo_tap", "bird_dove", "chime_wind", "leaf_rustle", "drop_deep"),
    )

    private val THEME_BY_ID: Map<String, Theme> = THEMES.associateBy { it.id }

    val THEME_IDS: Set<String> = THEMES.map { it.id }.toSet()

    fun theme(id: String?): Theme = THEME_BY_ID[id] ?: THEME_BY_ID.getValue(DEFAULT_THEME)

    // ------------------------------------------------------------------ har bir hodisaga alohida tanlov

    /** Hodisa tovushi mavzudagidek bo'ladi (standart). */
    const val OVERRIDE_THEME = "theme"

    /** Hodisa tovushi o'chiq: boshqa hodisalar eshitilaveradi. */
    const val OVERRIDE_OFF = "off"

    /** Hodisa uchun saqlanadigan qiymatlar: "theme", "off" yoki katalogdagi tovush id si (zaxira nusxani tekshirishda ham ishlatiladi). */
    val OVERRIDE_VALUES: Set<String> = linkedSetOf(OVERRIDE_THEME, OVERRIDE_OFF) + ALL.map { it.id }

    /** Hodisaning sozlamalardagi nomi. */
    fun eventTitleRes(kind: Earcons.Kind): Int = when (kind) {
        Earcons.Kind.FOCUS -> R.string.snd_event_focus
        Earcons.Kind.CLICK -> R.string.snd_event_click
        Earcons.Kind.EDGE -> R.string.snd_event_edge
        Earcons.Kind.WINDOW -> R.string.snd_event_window
        Earcons.Kind.SCROLL -> R.string.snd_event_scroll
        Earcons.Kind.ERROR -> R.string.snd_event_error
    }

    /** Hodisa uchun hozir ijro etiladigan tovush; null bo'lsa shu hodisa o'chirilgan (yoki saqlangan qiymat noma'lum). */
    fun resolve(context: Context, kind: Earcons.Kind): Sound? {
        val over = Prefs.earconOverride(context, kind)
        if (over == OVERRIDE_OFF) return null
        if (over != OVERRIDE_THEME) {
            val own = BY_ID[over]
            if (own != null) return own
        }
        return BY_ID[theme(Prefs.earconTheme(context)).soundId(kind)]
    }
}
