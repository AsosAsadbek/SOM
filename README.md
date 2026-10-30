# SO'M / SO'M/QV uchun ikki o'tishli assembler

Bu dastur **Soddalashtirilgan O'quv Mashinasi (SO'M)** va uning kengaytirilgan
varianti **SO'M/QV** (qo'shimcha vositali) uchun assembler tilida yozilgan
programmani mashina kodiga (ob'ekt programmaga) o'giradi.

> SO'M - bu Leland Beck'ning *"System Software: An Introduction to Systems
> Programming"* kitobidagi **SIC** (Simplified Instructional Computer), SO'M/QV
> esa **SIC/XE** (Extra Equipment). Internetda ma'lumot qidirsangiz shu
> nomlar bilan qidiring.

## Ishga tushirish

Python 3.8+ kerak, qo'shimcha kutubxona kerak emas.

```bash
python3 som_asm.py examples/copy_sic.asm      # standart SO'M programmasi
python3 som_asm.py examples/copy_xe.asm       # SO'M/QV programmasi
python3 som_asm.py examples/copy_csect.asm    # boshqaruv seksiyalari bilan
```

Natija ekranga chiqadi va ikkita fayl yoziladi:

* `*.lst` - listing (satr, adres, nishon, buyruq, operand, ob'ekt kodi) va SYMTAB;
* `*.obj` - ob'ekt programma (H, D, R, T, M, E yozuvlari).

Parametrlar: `--mode sic|xe|auto` (rejim, default avtomatik aniqlanadi),
`-o nom` (natija fayllari nomi), `--sep ""` (ob'ekt programmani `^` siz yozish).

Testlar: `python3 -m unittest discover tests`

## Mashina haqida qisqacha

| | SO'M | SO'M/QV |
|---|---|---|
| Xotira | 32 768 bayt (2^15) | 1 Mbayt (2^20) |
| So'z | 3 bayt = 24 bit | 3 bayt = 24 bit |
| Registrlar | A, X, L, PC, SW | + B, S, T, F |
| Buyruq formatlari | faqat 3 bayt | 1, 2, 3, 4 bayt |
| Adreslash | to'g'ridan-to'g'ri, indeksli | + Pc/baza ga nisbatan, bevosita (#), vositali (@) |

**SO'M buyrug'i (3 bayt):** `| opcode 8 | x 1 | adres 15 |`
Masalan `STL RETADR` → `14` + `x=0` + `1033` = **141033**.

**SO'M/QV 3-format:** `| opcode 6 | n i x b p e | disp 12 |`
**SO'M/QV 4-format** (`+` bilan): `| opcode 6 | n i x b p e | adres 20 |`

* `n i` - adreslash turi: `11` oddiy, `01` bevosita (`#`), `10` vositali (`@`);
* `x` - indeksli (`,X`); `b` - bazaga nisbatan; `p` - Pc ga nisbatan; `e` - 4-format.

Masalan `examples/copy_xe.asm` dagi `STL RETADR` (buyruq adresi 0000, RETADR = 0030):

* opcode `14` = `000101 00`, n=1, i=1 → birinchi bayt `000101 11` = **17**;
* PC = 0000 + 3 = 0003, `disp = TA - PC = 0030 - 0003 = 02D` (−2048..2047 oralig'ida);
* x=0 b=0 p=1 e=0 → `0010` = **2**;
* natija: **17202D**.

## Ikki o'tishli assembler qanday ishlaydi

`STL RETADR` satrini o'girish paytida `RETADR` hali uchramagan (u pastda
e'lon qilingan) - uning adresi noma'lum. Shu sababli assembler programmani
**ikki marta** o'qiydi:

**1-o'tish** (`Assembler.pass1`):
1. `LOCCTR` (adreslar hisoblagichi) = `START` operandi;
2. har bir satrga `LOCCTR` qiymati beriladi, nishon bo'lsa `SYMTAB` ga yoziladi;
3. `LOCCTR` buyruq uzunligiga oshiriladi: 3-format → 3, `+` → 4, `WORD` → 3,
   `RESW n` → 3n, `RESB n` → n, `BYTE C'EOF'` → 3;
4. `EQU`, `ORG`, `EXTDEF`, `EXTREF` direktivalari bajariladi;
   literallar (`=C'EOF'`) `LTORG` yoki `END` da xotiraga joylanadi.

**2-o'tish** (`Assembler.pass2`):
1. `OPTAB` dan buyruq kodi, `SYMTAB` dan operand adresi olinadi;
2. mashina kodi formatga mos yig'iladi (SO'M: `_encode_sic`,
   SO'M/QV: `_encode_format34`, `_encode_format2`);
3. `BYTE`/`WORD` qiymatlari hosil qilinadi;
4. ob'ekt programma va listing yoziladi.

**Jadvallar:**
* `OPTAB` (`som/optab.py`) - mnemonik → mashina kodi va format;
* `SYMTAB` (har bir seksiyada) - nishon → adres;
* `LOCCTR` - joriy adres.

## Ob'ekt programma yozuvlari

| Yozuv | Ma'nosi |
|---|---|
| `H^COPY  ^001000^00107A` | Bosh qism: nomi, boshlang'ich adresi, uzunligi |
| `T^001000^1E^141033^...` | Tana: boshlang'ich adres, uzunlik (≤ 30 bayt), kodlar |
| `D^BUFFER^000033^...` | EXTDEF: boshqa seksiyalar uchun e'lon qilingan nomlar |
| `R^RDREC ^WRREC` | EXTREF: bu seksiya murojaat qiladigan tashqi nomlar |
| `M^000004^05^+RDREC` | Modifikatsiya: yuklagich to'g'irlashi kerak bo'lgan adres |
| `E^001000` | Tugallash: birinchi bajariladigan buyruq adresi |

## Qo'llab-quvvatlanadigan imkoniyatlar

* barcha SO'M va SO'M/QV buyruqlari (1, 2, 3, 4-formatlar);
* adreslash: oddiy, `#` bevosita, `@` vositali, `,X` indeksli, Pc va bazaga
  nisbatan (`BASE`/`NOBASE`), `+` kengaytirilgan;
* direktivalar: `START END BYTE WORD RESB RESW EQU ORG LTORG BASE NOBASE CSECT EXTDEF EXTREF`;
* literallar: `=C'EOF'`, `=X'05'`, `=3`;
* ifodalar: `BUFEND-BUFFER`, `*`, `LENGTH+3`, `2*3`;
* boshqaruv seksiyalari (`CSECT`) va tashqi nomlar;
* xatolarni aniqlash: noma'lum buyruq, aniqlanmagan/ikki marta e'lon qilingan
  nom, sig'maydigan adres va h.k.

## Fayllar

```
som_asm.py            buyruqlar satri interfeysi
som/optab.py          OPTAB, registrlar, direktivalar
som/parser.py         satrni nishon/buyruq/operand/izohga ajratish
som/expr.py           ifodalarni hisoblash
som/assembler.py      1-o'tish, 2-o'tish, ob'ekt programma, listing
examples/             darslikdagi misol programmalar
tests/                natijalarni darslik bilan solishtiruvchi testlar
```

## Darslik matnidagi xatoliklar haqida

Berilgan hujjatdagi jadvallarda bir nechta xato bor (ob'ekt kodlar esa to'g'ri).
Misollar Beck kitobidagi asl variant bo'yicha yozilgan:

* SO'M programmasida `ENDFIL` nishoni 45-satrda (`LDA EOF`, adres 1015) bo'lishi
  kerak - `JEQ ENDFIL` kodi `301015`;
* `RDREC` nishoni 115-satrda (`LDX ZERO`, adres 2039), `RLOOP` esa 125-satrda
  (`TD INPUT`, adres 203F) bo'lishi kerak; `JEQ EXIT` kodi `302057`;
* RDREC seksiyasida `MAXLEN WORD BUFEND-BUFFER` (hujjatda `BUFEND-BUFEND`),
  seksiya uzunligi `00002B`;
* WRREC da `WD =X'05'` kodi `DF2008` (hujjatda `DF200B`).
