COPY     START   0               Fayl nusxasini olish (boshqaruv seksiyalari)
         EXTDEF  BUFFER,BUFEND,LENGTH
         EXTREF  RDREC,WRREC
FIRST    STL     RETADR          Qaytish adresini saqlash
CLOOP   +JSUB    RDREC           Berilganlarni o'qish
         LDA     LENGTH          O'qish tugaganligini aniqlash
         COMP    #0              EOF (LENGTH=0)
         JEQ     ENDFIL          EOF bo'lsa chiqish
        +JSUB    WRREC           Berilganlarni yozish
         J       CLOOP           Takrorlash
ENDFIL   LDA     =C'EOF'         Fayl oxiri belgisini yuklash
         STA     BUFFER
         LDA     #3              LENGTH = 3
         STA     LENGTH
        +JSUB    WRREC           EOF ni chiqarish
         J       @RETADR         Programmadan chiqish
RETADR   RESW    1
LENGTH   RESW    1               Yozuv uzunligi
         LTORG
BUFFER   RESB    4096
BUFEND   EQU     *               BUFEND qiymati joriy adresga teng
MAXLEN   EQU     BUFEND-BUFFER   MAXLEN adreslar ayirmasiga teng
*
RDREC    CSECT                   Boshqaruv seksiyasi boshi
*
*        Buferga yozuvni o'qish qism programmasi
*
         EXTREF  BUFFER,LENGTH,BUFEND
         CLEAR   X               Takrorlash hisoblagichiga 0
         CLEAR   A               A registrga 0
         CLEAR   S               S registrga 0
         LDT     MAXLEN          Yozuvning maksimal uzunligi
RLOOP    TD      INPUT           O'qish qurilmasini tekshirish
         JEQ     RLOOP           Tayyor bo'lguncha takrorlash
         RD      INPUT           A registrga belgini o'qish
         COMPR   A,S             Yozuv tugashini tekshirish
         JEQ     EXIT            Oxiri bo'lsa chiqish
        +STCH    BUFFER,X        Buferga belgini yozish
         TIXR    T               Yozuv maksimal uzunligigacha
         JLT     RLOOP           Takrorlash
EXIT    +STX     LENGTH          Yozuv uzunligi
         RSUB                    Qism programmadan qaytish
INPUT    BYTE    X'F1'           O'qish qurilmasi kodi
MAXLEN   WORD    BUFEND-BUFFER
*
WRREC    CSECT
*
*        Buferdagi yozuvni chiqarish qism programmasi
*
         EXTREF  LENGTH,BUFFER
         CLEAR   X               Takrorlash hisoblagichiga 0
        +LDT     LENGTH
WLOOP    TD      =X'05'          Yozish qurilmasini tekshirish
         JEQ     WLOOP           Tayyor bo'lguncha takrorlash
        +LDCH    BUFFER,X        Buferdan o'qish
         WD      =X'05'          Belgini yozish
         TIXR    T               Barcha belgilar yozilguncha
         JLT     WLOOP           Takrorlash
         RSUB                    Qism programmadan qaytish
         END     FIRST
