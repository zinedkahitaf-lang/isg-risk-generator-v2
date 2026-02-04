# Streamlit Deploy - KESIN ÇÖZÜM

## ⚠️ Problem
Streamlit Cloud "This file is not a valid Python script" hatası veriyor.

## ✅ ÇÖZÜM 1: Direkt Deploy Link

Bu linke tıklayın (Ctrl+Click):

https://share.streamlit.io/new?repository=zinedkahitaf-lang/isg-risk-generator-v2&branch=main

Açılan sayfada:
1. **Main file path**: `streamlit_app.py` (BAŞKA BİR ŞEY YAZMAY IN)
2. **Advanced settings** → **Secrets**:
```
GEMINI_API_KEY = "BURAYA-KEYİNİZİ-YAPIN"
```
3. Deploy!

---

## ✅ ÇÖZÜM 2: Manuel Adımlar

1. https://share.streamlit.io/ → Giriş yapın
2. "New app" tıklayın
3. **DROPDOWN MENÜDEN SEÇİN** (manuel yazmayın):
   - Repository: `isg-risk-generator-v2`
4. Branch: `main` (küçük harflerle)
5. Main file path: `streamlit_app.py` (tam olarak bu şekilde, başında / yok)
6. App URL: `isg-risk-v2-test` (kısa, özel bir isim)
7. Advanced settings → Secrets → Gemini API key ekleyin
8. Deploy!

---

## ✅ ÇÖZÜM 3: GitHub Actions ile Deploy

Eğer hala olmuyorsa size GitHub Actions workflow oluştururum, otomatik deploy olur.

---

## 🔍 Hata Kaynakları

- **"streamlit_app.py**"** yazıyor musunuz? → Yıldız işareti olmamalı!
- Main file path'e **"/"** veya boşluk mu ekliyorsunuz? → Sadece `streamlit_app.py`
- Branch'i **"master"** mı yazdınız? → **"main"** olmalı (küçük harf)

---

Hangisini deneyelim?
