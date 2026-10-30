COPY     START   0               Fayl nusxasini olish (SO'M/QV)
FIRST    STL     RETADR          Qaytish adresini saqlash
         LDB     #LENGTH         Baza registrini o'rnatish
         BASE    LENGTH
CLOOP   +JSUB    RDREC           Yozuvni o'qish
         LDA     LENGTH          Fayl tugaganligini tekshirish
         COMP    #0
         JEQ     ENDFIL          EOF bo'lsa chiqish
        +JSUB    WRREC           Yozuvni chiqarish
         J       CLOOP           Takrorlash
ENDFIL   LDA     EOF             Fayl oxiri belgisini yuklash
         STA     BUFFER
         LDA     #3              LENGTH = 3
         STA     LENGTH
        +JSUB    WRREC           EOF chiqarish
         J       @RETADR         Programmadan chiqish
EOF      BYTE    C'EOF'
RETADR   RESW    1
LENGTH   RESW    1               Yozuv uzunligi
BUFFER   RESB    4096            4096 baytli bufer
*
*        Buferga yozuvni o'qish qism programmasi
*
RDREC    CLEAR   X               Takrorlash hisoblagichiga 0
         CLEAR   A               A registrga 0
         CLEAR   S               S registrga 0
        +LDT     #4096
RLOOP    TD      INPUT           Kiritish qurilmasini tekshirish
         JEQ     RLOOP           Tayyor bo'lguncha takrorlash
         RD      INPUT           Belgini A registrga o'qish
         COMPR   A,S             Yozuv tugaganligini tekshirish
         JEQ     EXIT            Oxiri bo'lsa chiqish
         STCH    BUFFER,X        Belgini buferga yozish
         TIXR    T               Maksimal uzunlikkacha takrorlash
         JLT     RLOOP
EXIT     STX     LENGTH          Yozuv uzunligini saqlash
         RSUB                    Qism programmadan qaytish
INPUT    BYTE    X'F1'           Kiritish qurilmasi kodi
*
*        Buferdagi yozuvni chiqarish qism programmasi
*
WRREC    CLEAR   X
         LDT     LENGTH
WLOOP    TD      OUTPUT          Chiqarish qurilmasini tekshirish
         JEQ     WLOOP
         LDCH    BUFFER,X        Buferdan belgini olish
         WD      OUTPUT          Belgini chiqarish
         TIXR    T               Barcha belgilar chiqquncha
         JLT     WLOOP
         RSUB
OUTPUT   BYTE    X'05'           Chiqarish qurilmasi kodi
         END     FIRST
