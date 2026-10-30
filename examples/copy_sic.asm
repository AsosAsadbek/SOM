COPY     START   1000            Fayl nusxasini olish (standart SO'M)
FIRST    STL     RETADR          Qaytish adresini saqlash
CLOOP    JSUB    RDREC           O'qish programmasiga murojaat
         LDA     LENGTH          Kiruvchi ma'lumot tugaganligini
         COMP    ZERO            aniqlash (LENGTH=0)
         JEQ     ENDFIL          Berilganlarni o'qishni tugatish
         JSUB    WRREC           Berilganlarni chop qilish
         J       CLOOP           Takrorlash uchun o'tish
ENDFIL   LDA     EOF             Fayl oxiri belgisini yuklash
         STA     BUFFER
         LDA     THREE
         STA     LENGTH          LENGTH = 3
         JSUB    WRREC           EOF chiqarish
         LDL     RETADR          Qaytish adresini yuklash
         RSUB                    Programmadan chiqish
EOF      BYTE    C'EOF'
THREE    WORD    3
ZERO     WORD    0
RETADR   RESW    1
LENGTH   RESW    1               Yozuv uzunligi
BUFFER   RESB    4096            Bufer uzunligi - 4096 bayt
*
*        Buferga yozuvni o'qish programmasi
*
RDREC    LDX     ZERO            Takrorlanish sanagichi
         LDA     ZERO
RLOOP    TD      INPUT           Kiritish qurilmasini tekshirish
         JEQ     RLOOP           Tayyor bo'lguncha takrorlash
         RD      INPUT           Belgini A registrga o'qish
         COMP    ZERO            Yozuv tugaganligini tekshirish
         JEQ     EXIT            Takrorlashdan chiqish
         STCH    BUFFER,X        Belgini buferga yozish (X - siljish)
         TIX     MAXLEN          Takrorlash jarayoni
         JLT     RLOOP
EXIT     STX     LENGTH
         RSUB
INPUT    BYTE    X'F1'
MAXLEN   WORD    4096
*
*        Buferdagi yozuvni chiqarish qism programmasi
*
WRREC    LDX     ZERO
WLOOP    TD      OUTPUT
         JEQ     WLOOP
         LDCH    BUFFER,X
         WD      OUTPUT
         TIX     LENGTH
         JLT     WLOOP
         RSUB
OUTPUT   BYTE    X'05'
         END     FIRST
