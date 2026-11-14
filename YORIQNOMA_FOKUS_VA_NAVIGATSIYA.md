# Fokus va navigatsiya yo'riqnomasi (O'zbegim 0.9.19, v34)

Bu hujjat uch narsani aytadi: (1) teginib o'rganish va haqiqiy amalni bajarish o'rtasidagi muvozanat qanday qoidalarga tayanadi,
(2) v29 dagi qaysi nuqsonlar topildi va qanday tuzatildi, (3) tuzatishlarni telefonda qanday tekshirish kerak.

**Muhim:** bu muhitda Gradle bilan qurib ham, telefonda sinab ham bo'lmaydi. Kod kompilyator darajasida (yangi xato yo'qligi) va
mantiqiy modellar bilan tekshirildi. Sabablar jurnal va kodni o'qish orqali topilgan; ularning hech biri telefonda tasdiqlanmagan.
3-bo'limdagi sinov tartibi shuning uchun yozilgan: haqiqiy hukmni telefon beradi.

v31 (7-bo'lim): soat va batareya e'loni TalkBack bilan ham ishlashi va ikki marta bosish tasdig'i. 1-6-bo'limlar v30 holatini tasvirlaydi va
v31 da o'zgarmagan (faqat 6-bo'limdagi tebranish haqidagi band yangilandi).
v32 (8-bo'lim): tovush signallariga tabiat tovushlari va mavzular qo'shildi; "afzal ko'rilgan mexanizm" rejimida (TalkBack yoqiq) ham signal chalinadi.
v33 (9-bo'lim): tovushlar qayta yaratildi (uzunroq, tabiiyroq, variantli), iPhone uslubi va qadam tovushlari qo'shildi; aks sadoli tovushlar faqat uchta.
Fokus va navigatsiya mantig'i v32 da o'zgarmadi.

## 1. Qanday ishlaydi va muvozanat qoidalari

Teginib o'rganish yoqiq paytda har bir teginish ikki bosqichli ishdir:

1. **Tanlash.** Barmoq element ustida yuradi, tizim `TYPE_VIEW_HOVER_ENTER` yuboradi, O'zbegim elementga **fokus** beradi va o'qiydi.
   Bu bosqichda hech narsa bosilmaydi.
2. **Bajarish.** Foydalanuvchi **istalgan joyga ikki marta bosadi**, amal aynan fokusdagi (eng so'nggi eshitilgan) elementda bajariladi.
   Ikki marta bosishni kim bajarishi sozlanadi: Tafsilotlar > Bosish va navigatsiya ("Android tizimi bajaradi" yoki "O'zbegim bajaradi").

Muvozanat shu besh qoidaga tayanadi. Har bir tuzatish ulardan birini himoya qiladi:

| # | Qoida | Buzilganda foydalanuvchi nimani sezadi |
|---|-------|----------------------------------------|
| 1 | **Fokus faqat foydalanuvchining o'zi yoki yangi ekran uchun siljiydi.** Ilovaning tasodifiy hodisasi fokusni tortib olmaydi. | "Fokus mo'ljaldagi tugmadan qochib ketdi" |
| 2 | **Ikki marta bosish nishoni = oxirgi eshitilgan element.** Eskirgan yoki boshqa ekrandagi element nishon bo'lmaydi. | "Nomini eshitdim, lekin boshqa narsa bosildi" |
| 3 | **Bir ikki marta bosish = bitta amal.** Takror kelgan juftlik o'tkazib yuboriladi. | Kalit ikki marta almashib, holat o'zgarmay qoladi |
| 4 | **Bosish natijasi eshitiladi.** Holat yoki tugma nomi o'zgarsa, aytiladi. | "Amal bajarilmadi" deb qayta-qayta bosish |
| 5 | **Asosiy oqim band bo'lmaydi.** Hodisa ishlovi qisqa: barmoq ostidagi elementga fokus kechikmaydi. | Eshitish kechikadi, ikki marta bosish eski fokusga tushadi |

## 2. Topilgan nuqsonlar va tuzatishlar

Ishonch darajasi: **K** = kodni o'qib aniqlangan, **J** = jurnal ham ko'rsatadi, **T** = telefonda tasdiqlangan (hozircha hech biri).

| # | Nuqson | Sabab | Tuzatish | Fayl | Ishonch |
|---|--------|-------|----------|------|---------|
| 1 | Fokus klaviatura yoki tizim paneli ustidan "qochadi" | `maybeInitialFocus` oyna hodisasi kelgan har safar, fokus boshqa oynada (klaviatura, holat paneli, pastki tugmalar) bo'lsa ham, uni faol oynaning eng yuqori elementiga tortib olardi | Fokus klaviatura va tizim oynalarida turgan bo'lsa, barmoq tegib turgan bo'lsa yoki faol oyna klaviatura bo'lsa, siljitilmaydi | `ReaderService.maybeInitialFocus`, `focusInForeignWindow` | K |
| 2 | Dialog yoki menyu yopilgach fokus ekranning eng tepasiga sakraydi | Yopilgan oynadan qaytganda har doim birinchi elementga o'tilardi | Har oyna uchun oxirgi fokus eslab qolinadi; boshqa oynadan qaytilsa va element hali ko'rinsa, fokus unga qaytadi | `rememberWindowFocus`, `rememberedFocusFor` | K |
| 3 | Eski ekrandagi element bosilib ketadi | "Yumshoq fokus" (tizim fokus bermagan, o'zimiz o'qigan element) 120 soniya saqlanardi; ilovaning manbasiz fokus hodisasi uni tozalamasdi; ekran almashganda ham qolardi | Muddat 45 soniya; manbasiz fokus hodisasi tozalaydi; ekran almashganda yangilab bo'lmaydigan yumshoq fokus tashlanadi | `onFocused`, `currentFocus`, `dropStaleSoftFocus` | K |
| 4 | Kalit ikki marta almashadi, tugma ikki marta bosiladi | "O'zbegim bajaradi" rejimida ikki marta bosish takror kelgan: jurnalda 63 ta bosish orasidagi 62 ta oraliqning 5 tasi 350 ms dan qisqa (72, 268, 269, 280 va 316 ms); odam uchun bunday tez takror deyarli mumkin emas | 350 ms ichida kelgan ikkinchi juftlik o'tkazib yuboriladi (`dt_dup`) | `handleGesture` | J |
| 5 | Ikki marta bosish hali qayta ishlanmagan oxirgi teginishga tushmaydi | Barmoq tez ko'tarilganda oxirgi hover hodisasi navbatda turgan bo'lishi mumkin | Ikki marta bosishdan oldin kutayotgan hover yakunlanadi | `activateByDoubleTap` | K |
| 6 | Bosdim, hech narsa eshitilmadi, shuning uchun qayta bosdim | Tugma nomi o'zgarsa ("Pauza" -> "Ijro"), O'zbegim faqat holat o'zgarganda gapirardi. Jurnalda YouTube'da 25 ta bosish bor, ulardan 12 tasi oldingisidan 1,5 soniya ichida (qayta bosish ehtimoli) | Bosishdan keyin 2,5 soniya ichida bosiladigan elementning o'z nomi o'zgarsa, yangi nom aytiladi (TalkBack kabi). Vaqt yoki hisoblagich kabi o'zi o'zgaradigan matn aytilmaydi | `checkStateChange`, `labelKey` | J |
| 7 | Eshitish va fokus kechikadi | Hodisa ishlovi daraxtni qayta-qayta yurardi (`related`/`isInside`): jurnalda 9 ta `SLOW_HANDLER`, eng uzuni 364 ms; ular hover ishlovini kutdirgan bo'lishi mumkin | Oyna raqami bo'yicha tez rad etish, rejalashtirilgan tekshiruv paytida yurmaslik, yurish chuqurligi 12 | `related`, `scheduleStateCheck`, `isInside` | K, J qisman |
| 8 | Select to Speak yoqilsa O'zbegim jim qoladi | Google paketidagi har qanday xizmat "TalkBack" hisoblanardi | Qaror xizmat (paket + sinf) bo'yicha; yordamchi xizmatlar hisobga olinmaydi (5-bo'lim) | `ReaderRules`, `OtherReaders` | K |
| 9 | Bosh ekrandagi eslatma | O'zbegim boshqa ekran o'quvchi bilan o'zi almashinadi, eslatma eskirgan | Olib tashlandi (maket va 4 tildagi matn) | `activity_main.xml`, `strings.xml` | |

## 3. Telefonda sinash tartibi

Har sinovdan keyin natijani yozib boring. Sinovlarni **ikkala rejimda** (Tafsilotlar > Bosish va navigatsiya) takrorlang: 5, 6 va 7-sinovlar rejimga bog'liq.

1. **TalkBack bilan almashinuv.** O'zbegim yoqiq, TalkBack o'chiq. Sozlamalardan TalkBack'ni yoqing.
   Kutiladi: bir-uch soniyada "Boshqa ekran o'quvchi ishni boshladi, men ekranni o'qishni to'xtatdim", keyin faqat TalkBack gapiradi.
   TalkBack'ni o'chiring. Kutiladi: bir necha soniyada "Men ekranni o'qishni boshladim, boshqa ekran o'quvchi dastur o'chirilganligi uchun".
2. **Select to Speak.** TalkBack o'chiq, Select to Speak'ni yoqing. Kutiladi: O'zbegim to'xtamaydi, odatdagidek o'qiydi.
3. **Klaviatura.** Xabar yozish maydonini oching, klaviatura chiqsin, tugmalarni barmoq bilan tekshiring, bir necha soniya kuting (ilova
   takliflar chiqarishi mumkin). Kutiladi: fokus klaviaturada qoladi, ilovaning yuqori qismiga sakramaydi.
4. **Dialog yoki menyu yopilishi.** "Qo'shimcha" (uch nuqta) menyusini oching, Orqaga bilan yoping. Kutiladi: fokus uch nuqta tugmasiga
   qaytadi, ekranning birinchi elementiga emas.
5. **Orqaga qaytish.** Sozlamalarda biror qatorni oching, Orqaga bosing. Kutiladi: fokus ochgan qatoringizda.
6. **Bosish natijasi.** YouTube'da pauza/ijro tugmasini ikki marta bosing; Wi-Fi kalitini ham. Kutiladi: yangi nom ("Ijro") yoki holat aytiladi.
7. **Takror.** "O'zbegim bajaradi" rejimida kalitni tez-tez ikki marta bosing. Kutiladi: har juftlik bitta almashtirish, tez takror o'tkazib yuboriladi.
8. **Oxirgi eshitilgan.** A elementga tegib eshiting, tezda B ga o'ting, eshiting, barmoqni ko'tarib ikki marta bosing. Kutiladi: B bosiladi.
9. **Pastki tugmalar.** Pastki (Orqaga, Bosh ekran) tugmalarni teginib toping, YouTube'da video o'ynab turganda. Kutiladi: fokus tugmada qoladi.
10. **Jurnal.** Sinovdan keyin "Xatolar jurnali" ekranidan ulashing (4-bo'lim bo'yicha o'qiladi).

## 4. Jurnalni o'qish (`GESTURE_PATH`)

| Yozuv | Ma'nosi |
|-------|---------|
| `dt_click`, `dt_global`, `dt_touch` | "O'zbegim bajaradi" rejimida bosish yo'li: element bosildi, tizim tugmasi bajarildi yoki sun'iy tegish yuborildi |
| `sys_click` (yangi) | "Android tizimi bajaradi" rejimida ilova bosish hodisasini yubordi. `rel=true`: bosilgan element fokusdagi element bilan qarindosh. `rel=false` ko'p bo'lsa, bosish eshitilgan elementga tushmayapti, ya'ni fokus qochgan. Jurnal hajmi cheklangan: `rel=false` 0,7 soniyada, `rel=true` 15 soniyada bir martadan ko'p yozilmaydi, shuning uchun yozuvlar sonini bosishlar soni deb o'qimang |
| `dt_dup` (qora quti) | Takror ikki marta bosish o'tkazib yuborildi |
| `SLOW_HANDLER` | Hodisa ishlovi 120 ms dan uzoq. Soni kamayganini solishtiring: v29 jurnalida 9 ta, eng uzuni 364 ms |

Eslatma: v29 jurnalida bosish yozuvlari (`dt_*`) bor, demak u paytda rejim "O'zbegim bajaradi" bo'lgan. "Tizimga berilganda ham qiyin" degan
kuzatuvingizni tizim rejimi jurnali hali ko'rsatmaydi (v29 da bunday bosish yozilmasdi). Shu sababli `sys_click` qo'shildi: keyingi
jurnalni tizim rejimida yozing.

## 5. Boshqa ekran o'quvchi bilan almashinish qoidalari

- **Xizmat bo'yicha qaror** (paket nomi bo'yicha emas). Ekran o'quvchi hisoblanadi: TalkBack (sinf nomi `TalkBackService`), Samsung TalkBack va
  Voice Assistant, Jieshuo, Dianming: ular to'xtatilgan (suspend) bo'lsa ham; noma'lum xizmat esa faqat hozir teginib o'rganishni talab qilsagina.
- **Hisobga olinmaydi:** Select to Speak, Switch Access, Voice Access, Accessibility Menu, Braille xizmatlari, Universal Switch, Assistant menu.
- **Yoqilganda tezroq:** sozlamalarda yoqilgan, lekin tizim hali ulamagan ma'lum ekran o'quvchi 15 soniyagacha hisobga olinadi (tez to'xtash uchun).
  15 soniyada ham ulanmasa, u ishlamayapti deb hisoblanadi va O'zbegim jim qolmaydi.
- **O'chirilganda tezroq:** sozlamalardan olib tashlangan xizmat tizimdan hali uzilmagan bo'lsa ham hisobga olinmaydi.
- O'zbegim kutish rejimidan chiqqanda ikki marta bosish sozlamasini qayta moslaydi (kutish paytida o'zgartirilgan bo'lishi mumkin).

## 6. Cheklovlar va keyingi qadamlar (halol)

- Bu muhitda Gradle qurilmasi va telefon yo'q: **qurilmadagi xatti-harakat tasdiqlanmagan.** Qurishda xato chiqsa, xato matnini yuboring.
- Ikki marta bosish standarti "Android tizimi bajaradi" bo'lib qoldi. Qaysi rejim sizning telefoningizda qulay ekanini 3-bo'limdagi sinovlar ko'rsatadi.
- O'zgartirilmadi: `dt_touch` sun'iy tegish yo'li (teginib o'rganishni vaqtincha o'chiradi); TTS `ERROR_OUTPUT` (-5) xatosi (jurnalda 1 marta);
  hover ishlovi asosiy oqimda qoldi. (Bosish tasdig'i uchun tebranish va tovush v31 da qo'shildi: 7.3.)
- Agar sinovdan keyin ham fokus qochsa, jurnal va qaysi sinov (raqami) va rejimni yuboring: keyingi tuzatish shu ma'lumotga tayanadi.

## 7. v31: mustaqil o'quvchini TalkBack + O'zbegim dvigateli qulayligiga yaqinlashtirish va soat/batareya e'loni

### 7.1 Kuzatuv va tahlil

Kuzatuv: O'zbegim "Afzal ko'rilgan mexanizm" bo'lib, ekran o'quvchi TalkBack bo'lganda bosish, harakatlanish va nutq qulay; O'zbegimning o'zi
ekran o'quvchi bo'lganda qulay emas, shuning uchun uni tanlamaydilar. Shu holatda soat va batareya e'loni ishlamaydi.

Nega farq bor (kodni o'qib, telefonda tasdiqlanmagan):

| | TalkBack + O'zbegim dvigateli | O'zbegim mustaqil |
|---|---|---|
| Teginish, fokus, navigatsiya, ikki marta bosish | TalkBack (Google'ning pishgan kodi, alohida jarayon) | `ReaderService` (~5100 qator, asosiy oqimda, o'z navigatori va Telegram uchun ko'p maxsus qoidalar) |
| O'zbegim nima qiladi | Faqat matnni tayyorlaydi va ovoz beradi (`OzbegimTtsService`) | Hammasini: o'qiydi, harakatlantiradi, bosadi, e'lon qiladi |

Shuning uchun mustaqil o'quvchini TalkBack tuzilmasiga "ko'chirib" bo'lmaydi: TalkBack alohida dastur, O'zbegimning ekran o'quvchisi esa o'z
navigatoriga ega. Haqiqiy yaqinlashish yo'li: nima sekin yoki noqulayligini o'lchash va tuzatish. v31 shu yo'ldagi birinchi qadam.

v30 jurnalidan (65 yozuv) aniq raqamlar:

- Bosish yo'llari ishlayapti: `sys_click` 12 (hammasi `rel=true`, ya'ni fokusdagi elementga tushgan), `dt_click` 14, `dt_global` 8, `dt_touch` 2; `FOCUS_NODE_FAILED` yo'q.
- Ishora ishlovi sekin: `SLOW_HANDLER` 7 ta. Ishoralar: o'ngga surish 413 va 137 ms, chapga surish 233 ms, ikki marta bosish 149 ms. Hodisalar
  (`TYPE_WINDOW_CONTENT_CHANGED`): 174, 167, 179 ms. `LATENCY_BUDGET`: 409 ms (1 ta).
- Bosish bajarilganini bildiradigan hech narsa yo'q edi (tebranish yoki tovush): TalkBack'da bor.
- `TTS_ENGINE_ERROR` -5 (1 ta): qora quti izida undan 19 ms oldin kutish rejimiga o'tish (`yield`) bor.

Jurnal mustaqil rejimda bitta aniq nosozlikni ko'rsatmaydi: bosishlar bajarilgan, fokus berishda istisno yo'q. U faqat kechikishni (7 ta sekin ishlov)
va tasdiq yo'qligini ko'rsatadi. "Qulaylik" farqining to'liq sababi uchun 7.4 dagi o'lchov kerak; shu sababli v31 faqat dalil bor joyni o'zgartirdi.

### 7.2 Soat va batareya e'loni (B)

Sabab: e'lon faqat `ReaderService` orqali aytilardi. TalkBack yoqilganda u kutish rejimiga o'tadi va u yerda `speak()` jim; xizmat o'chirilgan
bo'lsa jadvalni ushlab turadigan hech narsa yo'q edi. Dvigatel jadvalga umuman aloqasi yo'q edi.

v31 da:
- Jadvalni ikki ega ushlab turadi: ekran o'quvchi xizmati va O'zbegim dvigateli. O'zbegim afzal ko'rilgan mexanizm bo'lsa, TalkBack ishlab turganda
  dvigatelga odatda ulanib turadi (Android'ning odatiy xatti-harakati, telefonda tasdiqlanmagan), shuning uchun jadval ekran o'quvchi xizmati
  o'chiq bo'lsa ham ishlaydi. Dvigatel jarayoni to'xtab qolsa ham, **soat** e'loni alarm orqali davom etadi (alarm jarayonni qayta ishga tushiradi).
  **Batareya** e'loni esa batareya hodisasini kuzatuvchi ega tirik bo'lgandagina ishlaydi (xizmat yoki dvigatel ulangan bo'lishi kerak).
- Ekran o'quvchi xizmati yoqiq bo'lsa (kutish rejimida ham) e'lonni o'zi aytadi. Faqat O'zbegimni o'zingiz to'xtatgan bo'lsangiz jim turadi.
- Xizmat yo'q bo'lsa, "yordamchi ovoz" aytadi: telefondagi haqiqiy dvigatel orqali (O'zbegimning o'zi emas), O'zbegim matn qoidalari bilan.
- TalkBack gapirayotganda e'lon uning tanaffusini kutadi (dvigatel 0,7 soniya jim bo'lguncha). TalkBack'ning gapini **to'xtata olmaymiz**:
  "Matn o'qilayotgan bo'lsa kutish" bo'lsa 2 daqiqagacha kutadi, "darhol ayt" bo'lsa 4 soniyagacha.
- Alarm signali e'lon tugaguncha (9 soniyagacha) ushlab turiladi: jarayon signal uchun yangi ishga tushsa ham e'lon yo'qolmaydi.
- O'zbegim ishlatilmayotgan bo'lsa (afzal ko'rilgan mexanizm emas va xizmat ham yoqilmagan), alarm zanjiri o'zi to'xtaydi.

**Cheklov:** O'zbegimning ekran o'quvchiga bog'liq boshqa imkoniyatlari (menyu, o'z ishoralari, ekran bo'yicha qidiruv va boshqalar) TalkBack
ekran o'quvchi bo'lganda ishlay olmaydi: ular ekranni boshqarishni talab qiladi. Soat va batareya e'loni kabi "o'quvchisiz" ishlay oladigan
narsalar ko'chirildi. Yana qaysi imkoniyat yetishmayotganini yozsangiz, ko'rib chiqaman.

### 7.3 Ikki marta bosish tasdig'i (A)

TalkBack'da element faollashganda qisqa titraydi; O'zbegimda hech narsa yo'q edi: tugma nomi o'zgarmasa foydalanuvchi "bosilmadi" deb qayta bosardi.
v31 da: Sozlamalar > "Bosganda titrash (tasdiq)" (standart: yoqiq) va "Tovush signallari" (standart: o'chiq) yoqilgan bo'lsa qisqa ikki pog'onali tovush.
Tasdiq "O'zbegim bajaradi" rejimida bosish bajarilgan zahoti, "Android tizimi bajaradi" rejimida ilovadan bosish hodisasi kelganda (ekranga yaqinda
tegilgan bo'lsa) beriladi; bir bosish uchun ikki marta berilmaydi.

### 7.4 Sekinlik sababini topish: yangi jurnal maydonlari

`SLOW_HANDLER` (ishora uchun) endi qo'shimcha maydonlar beradi (millisekund):

| Maydon | Nimaga ketgan vaqt |
|--------|--------------------|
| `ms` | Ishoraning umumiy ishlov vaqti |
| `cur` | Joriy fokusli elementni topish |
| `nav` | Navigatorning keyingi/oldingi elementni qidirishi |
| `act` | Tizimga "fokus ber" amalini yuborish (ilova javobini kutadi) |
| `ms` - (`cur`+`nav`+`act`) | Qolgan ishlar: ro'yxat tartibi, aylantirish, nutqni tayyorlash |

Qaysi maydon katta bo'lsa, keyingi tuzatish shu yerga qaratiladi (masalan, `act` katta bo'lsa kechikishni ilova beryapti va O'zbegim buni
o'zgartira olmaydi; `nav` katta bo'lsa navigatorni tezlashtirish mumkin). Navigatorni ko'r-ko'rona qayta yozish yaxshilashdan ko'ra buzish
xavfi yuqori: shuning uchun v31 da u o'zgartirilmadi.

### 7.5 Telefonda sinash (v31)

Qurish va o'rnatishdan keyin:

1. **Soat/batareya, TalkBack + O'zbegim dvigateli, O'zbegim xizmati o'chiq.** Sozlamalar > Matnni nutqqa aylantirish: O'zbegim; TalkBack yoqiq;
   O'zbegim ekran o'quvchi xizmati o'chiq. O'zbegim > Soat va batareya: yoqing, "Hozir ayt" yoki sinov tugmasini bosing. Kutiladi: e'lon eshitiladi.
2. **Xuddi shu, O'zbegim xizmati yoqiq (kutish rejimida).** Kutiladi: e'lon eshitiladi (v30 da jim edi).
3. **Ekran o'chiq.** Ekranni qulflab, kelgan e'lon vaqtini kuting (masalan, har 5 daqiqada). Kutiladi: e'lon eshitiladi; eshitilmasa, jurnalni yuboring.
4. **TalkBack gapirayotganda.** Uzun matn o'qitib turing, shu paytda e'lon vaqti kelsin. Kutiladi: e'lon TalkBack tanaffusidan keyin eshitiladi,
   aralashib ketmaydi.
5. **Bosish tasdig'i, ikkala rejim.** O'zbegim mustaqil, biror tugmani ikki marta bosing, "Bosganda titrash" yoqiq. Kutiladi: bosish bilan qisqa titroq.
   "Tovush signallari"ni ham yoqib sinang. Kutiladi: qisqa "tak-tuk" tovushi. Har bosishda bir marta; ikki marta bo'lsa, qaysi rejim ekanini yozing.
6. **Jurnal.** Bir necha daqiqa ishlatgach "Xatolar jurnali"dan ulashing: `SLOW_HANDLER` dagi `cur`/`nav`/`act` maydonlari keyingi qadamni belgilaydi.

### 7.6 Tekshirilganlik

- Kompilyator darajasida: `kotlinc` 2.0.21 (Android SDK siz), v30 bilan solishtirildi: sintaksis xatosi yo'q; yangi xatolar faqat Android
  turlariga havolalar va ulardan kelib chiqqan zanjirli xatolar.
- **Tekshirilmagan:** Gradle bilan qurish va telefondagi xatti-harakat (TalkBack bilan aralashmaslik vaqti, ekran o'chiq paytida e'lon, tebranish kuchi,
  mustaqil rejimda kechikish o'zgarishi). Bu muhitda ikkalasi ham mumkin emas.

## 8. v32: tovush signallari (tabiat tovushlari) va afzal ko'rilgan mexanizm rejimi

### 8.1 Nima o'zgardi

Foydalanuvchi so'rovi: "Tovush signallari" ga tomchi, suv sathiga urilish va boshqa hordiq beradigan tabiat tovushlari qo'shilsin; O'zbegim afzal ko'rilgan
mexanizm bo'lganda (TalkBack yoqiq) ham ular ishlasin. Sabab va tuzilma: README 0.9.17 bo'limi, ARXITEKTURA.md 19-bo'lim.

Sozlamalar > "Tovush signallari sozlamalari": asosiy tugma, mavzu (Klassik, Suv va tomchilar, Yomg'ir, O'rmon va qushlar, Sokinlik, Aralash tabiat), balandlik,
6 hodisa uchun alohida tovush (yoki "O'chiq"), katalogdagi 28 tovushni (v33 da 53) tinglash ro'yxati, "TalkBack yoqiq bo'lganda ham signal chalish" tugmasi.

### 8.2 Qaysi hodisaga qachon signal chalinadi

| Hodisa | O'zbegim o'zi o'qiyotganda | TalkBack yoqiq (afzal ko'rilgan mexanizm) |
|---|---|---|
| Fokus | har yangi elementda | har yangi elementda (`TYPE_VIEW_ACCESSIBILITY_FOCUSED`) |
| Bosish | ikki marta bosish bajarilganda | ilovadan bosish hodisasi kelganda (`TYPE_VIEW_CLICKED`) |
| Chegara | ro'yxatning boshi yoki oxiriga yetganda | yo'q |
| Oyna | yangi oyna yoki ekranda | yangi oyna sarlavhasida (`TYPE_WINDOW_STATE_CHANGED`) |
| Surish | ro'yxat surilganda (yangi) | ro'yxat surilganda (`TYPE_VIEW_SCROLLED`, surish boshida bir marta) |
| Xato | "fokus yo'q", "amal bajarilmadi" (yangi) | yo'q |

TalkBack ustunidagi signallar uchun hamma shart bajarilgan bo'lishi kerak: "Tovush signallari" yoqiq, "TalkBack yoqiq bo'lganda ham signal chalish" yoqiq,
O'zbegim maxsus imkoniyatlar xizmati yoqiq. Biri yetishmasa, sozlamalar ekranidagi "Holat" matni nima yetishmasligini aytadi.

### 8.3 Telefonda sinash (v32)

1. **Asosiy rejim (O'zbegim mustaqil).** Sozlamalar > Tovush signallari sozlamalari: asosiy tugmani yoqing, mavzuni "Suv va tomchilar" ga o'zgartiring.
   Kutiladi: 6 ta tovush ketma-ket eshitiladi (tomchilar). Ekranda yuring, tugma bosing, ro'yxatni suring, oyna almashtiring: har hodisaga tegishli tovush chalinadi.
2. **Balandlik.** Surgichni suring (350 ms to'xtagach sinov tovushi chalinadi) va "Balandlikni aniq son bilan kiritish" oynasini sinang (+1, +10, Sinash).
   Kutiladi: tovush nutqdan baland yoki past bo'lib ketmaydi; telefondagi "maxsus imkoniyatlar" ovoz balandligi tovushga ham ta'sir qiladi.
3. **Hodisaga tovush.** "Fokus o'zgarganda" ni "Qush chiyillashi" ga o'zgartiring: darhol shu tovush chalinadi; "O'chiq" qiling: fokus jim bo'ladi, boshqalari eshitiladi.
4. **Tinglash ro'yxati.** 28 tovushni birma-bir bosing. Eshitib baho bering: tabiiymi, yoqimlimi, bir-biridan sezilarli baland yoki past emasmi, zerikarli takrorlanmayaptimi.
   Yoqmaganini yozing: almashtiriladi (skriptdagi `s_<id>` funksiyasini o'zgartirib, `python3 tools/make_sounds.py` bilan qayta hosil qilinadi).
5. **Afzal ko'rilgan mexanizm rejimi.** O'zbegim afzal ko'rilgan mexanizm; TalkBack yoqiq; O'zbegim maxsus imkoniyatlar xizmati yoqiq; sozlamalarda "TalkBack yoqiq bo'lganda ham signal chalish" yoqiq.
   TalkBack bilan yuring. Kutiladi: har yangi elementda fokus tovushi, ro'yxat surilganda bir marta surish tovushi, yangi oynada oyna tovushi.
   - Hech qanday tovush chalinmasa: "Holat" matnini o'qing; xizmat yoqiqligini tekshiring; bo'lmasa jurnalni yuboring (hodisalar yetib kelmayotgan bo'lishi mumkin).
   - Bir hodisaga ikki tovush eshitilsa: TalkBack sozlamalarida "Sound feedback" ni o'chiring.
   - Telefon sekinlashsa yoki TalkBack kechiksa: "TalkBack yoqiq bo'lganda ham signal chalish" ni o'chiring (v31 dagi xatti-harakat qaytadi) va yozing.
6. **Yangilanish.** "Tovush signallari" oldindan yoqilgan bo'lsa, endi surish va xato signali ham chiqadi. Xalaqit bersa, hodisa ro'yxatidan "O'chiq" qiling.
7. **Jurnal.** Bir necha daqiqa ishlatgach "Xatolar jurnali"dan ulashing: `EARCON_LOAD` bo'lsa, qaysi tovush yuklanmagani yoziladi; `FOCUS_NODE_FAILED` dagi `stale` maydoni
   fokus xatosining sababini ajratadi.

### 8.4 Tekshirilganlik

- Resurslar va kod: README 0.9.17 "Tekshiruv (v32)" bandi (Python tekshiruvi, `kotlinc` bilan v31 ga solishtirish: yangi xato yo'q).
- **Tekshirilmagan:** Gradle bilan qurish va telefondagi xatti-harakat: tovushlarning haqiqiy eshitilishi va yoqimliligi, TalkBack bilan hodisalarning yetib kelishi,
  ikki marta eshitilish, kutish rejimida tezlik. Bu muhitda ularning birortasi mumkin emas.

## 9. v33: tovushlar tabiiyroq va uzunroq, iPhone uslubi, qadam tovushlari

### 9.1 Nima o'zgardi

Foydalanuvchi so'rovi: harakatlanish va bosish tovushlari tabiiyroq, batafsilroq va kengroq eshitiladigan bo'lsin (tomchi va suv "kichik joyda" bo'layotgandek, yaratilgandek tuyuladi);
iPhone tovushlari qo'shilsin; hamma tovush aks sadoli bo'lmasin. Sabab va tuzilma: README 0.9.18 bo'limi, ARXITEKTURA.md 20-bo'lim.

Sozlamalar > "Tovush signallari sozlamalari": mavzular 8 ta (yangi: **iPhone uslubi**, **Qadamlar va yog'och**), katalog 53 tovush (yangi guruhlar: "iPhone uslubidagi tovushlar",
"Qadam va harakat tovushlari"). Mavjud tovushlar yangi usulda qayta yaratildi (o'rtacha 3,5 baravar uzunroq, 3,7 dB baland; nomlari va saqlangan sozlamalar o'zgarmadi), ko'pining
2-4 varianti bor (ilova ularni navbat bilan chaladi). Aks sadoli tovushlar faqat uchta: "Chuqur tomchi", "G'orda tomchi", "Shamol qo'ng'irog'i" (nomida yozilgan). Standart mavzu o'zgarmadi (Klassik).

### 9.2 Telefonda sinash (v33)

1. **iPhone uslubi.** Mavzuni "iPhone uslubi" ga o'zgartiring: 6 tovush ketma-ket eshitiladi. Fokus (tik), bosish (pop), ro'yxat oxiri (past zarba), yangi oyna (shamolcha va shisha ohangi),
   surish (tiqirlash), xato (ikki past tuk). Baholang: yumshoqmi, yasama emasmi, nutqni bosib ketmaydimi. Eslatma: bular Apple tovushlari emas, ularning xarakteriga yaqin asl sintez.
2. **Qadamlar.** Mavzuni "Qadamlar va yog'och" ga o'zgartiring va ro'yxatda yuring: har fokusda o'tloqdagi qadam, bosishda yog'och taqillashi, ro'yxat oxirida yog'och polda qadam.
3. **Suv va tomchilar, Yomg'ir.** Eski mavzularni qayta sinang: tomchi endi "kichik joyda" emasmi, uzunroq so'nadimi, suv tabiiyroqmi, yomg'ir tomchisi va barglar kengroqmi.
4. **Takrorlanish.** Bitta tovushni (masalan, "Mayda tomchi") ketma-ket 6-8 marta bosing: variantlar almashadi, tovush "mashinadek" takrorlanmaydi.
5. **Aks sado.** Tinglash ro'yxatidagi hamma tovushni eshiting: aks sadoli faqat nomida shunday yozilgan uchtasi bo'lishi kerak. Boshqasida aks sado sezilsa, nomini yozing.
6. **Balandlik.** Mavzular orasida bir tovush ikkinchisidan sezilarli baland yoki past chiqmasligi kerak. "iPhone: past zarba" va "Yog'och polda qadam" bir oz sust bo'lishi mumkin (README 0.9.18 "Ma'lum kamchiliklar").
7. **Hajm va yuklanish.** Ilova yangilangach tovushlar birinchi chalinishda biroz kechikishi mumkin (hamma variant yuklanadi): shunda birinchi signal tushib qolishi normal; keyingilari darhol.
   `EARCON_LOAD` jurnalda chiqsa, qaysi tovush (variant raqami bilan) yuklanmagani yoziladi.

### 9.3 Tekshirilganlik

- Resurslar va kod: README 0.9.18 "Tekshiruv (v33)" bandi (Python tekshiruvi, `kotlinc` bilan `Sounds.kt` va `Earcons.kt`: xato va ogohlantirish yo'q).
- **Tekshirilmagan:** Gradle bilan qurish; tovushlarni quloq bilan eshitish (tabiiylik, yoqimlilik, "yasama" emasligi): bu muhitda eshitib bo'lmaydi, hukm sizniki; telefondagi xatti-harakat.

## 10. v34: RHVoice ruscha ovozlar va dvigatel bilan aloqa

Sabab va tuzilma: README 0.9.19 bo'limi, ARXITEKTURA.md 21-bo'lim. Fokus va navigatsiyaga tegilmagan; quyida faqat ovoz tanlash va tizim dvigateli.

1. **Ro'yxat yangilanishi.** RHVoice da rus tilini yuklab oling, O'zbegim > Ovozlar ga qayting: ro'yxat o'zi yangilanadimi, ruscha ovoz "(ru-RU)" bilan chiqadimi. Ruscha ovozda "Tinglash"
   ruscha namuna aytadimi.
2. **Har til uchun ovoz.** Ruscha ovozni, keyin o'zbekcha ovozni tanlang. O'zbegim afzal ko'rilgan mexanizm bo'lsin. Boshqa ilovada ruscha matn ruscha ovozda, o'zbekcha matn o'zbek
   ovozida aytiladimi. Sozlamalar > Matnni nutqqa aylantirish > O'zbegim: tillar ro'yxatida rus tili bormi.
3. **Aloqa uzilishi.** RHVoice da paket yuklanayotganda yoki yangilanayotganda gapirtirib ko'ring: bir necha soniya sukunatdan keyin nutq o'zi tiklanadimi (oldin tiklanmasligi mumkin edi).
4. **"Standart ovoz" tugmasi** ikkala tilning tanlovini tozalaydimi (keyin ruscha matn dvigatelning standart ruscha ovozida aytiladi).
5. **Jurnal.** Muammo bo'lsa, Xatolar jurnalini yuboring: `TTS_SERVICE_ERROR` dagi `why`, `lang`, `code`, `langs` (dvigatel bergan tillar) maydonlari sababni ko'rsatadi.
