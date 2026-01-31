import streamlit as st
import google.generativeai as genai
import json
import io
import time
import gc
import httpx
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Sayfa Ayarları
st.set_page_config(
    page_title="İSG Risk Değerlendirme Asistanı",
    page_icon="🛡️",
    layout="wide"
)

# === YARDIMCI FONKSİYONLAR ===

# Fine Kinney Risk Seviyeleri
RISK_LEVELS = {
    "tolerans_gosterilemez": {"min": 400, "max": float('inf'), "color": "FFFF0000", "label": "Tolerans Gösterilemez Risk"},
    "esasli": {"min": 200, "max": 400, "color": "FF808080", "label": "Esaslı Risk"},
    "onemli": {"min": 70, "max": 200, "color": "FF0070C0", "label": "Önemli Risk"},
    "olasi": {"min": 20, "max": 70, "color": "FFFFFF00", "label": "Olası Risk"},
    "onemsiz": {"min": 0, "max": 20, "color": "FF00B050", "label": "Önemsiz Risk"}
}

def get_risk_level(score):
    if score > 400: return RISK_LEVELS["tolerans_gosterilemez"]
    elif score > 200: return RISK_LEVELS["esasli"]
    elif score > 70: return RISK_LEVELS["onemli"]
    elif score > 20: return RISK_LEVELS["olasi"]
    else: return RISK_LEVELS["onemsiz"]

def create_excel(risk_data, workplace):
    wb = Workbook()
    ws = wb.active
    ws.title = "Risk Değerlendirme"
    
    headers = [
        "Sıra No", "Faaliyet Alanı", "Faaliyet Türü", 
        "Tehlike Tanımı", "Risk Tanımı (Olası Etki)",
        "O", "F", "Ş", "R", "Riskin Tanımı",
        "Planlanan Faaliyetler / DÖF", "Sorumlu", "Süre",
        "Sonraki O", "Sonraki F", "Sonraki Ş", "Sonraki R", "Sonraki Riskin Tanımı"
    ]
    ws.append(headers)
    
    # Stiller
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    for item in risk_data:
        o = float(item.get('olasilik', 1))
        f = float(item.get('frekans', 1))
        s = float(item.get('siddet', 1))
        current_score = o * f * s
        current_level = get_risk_level(current_score)
        
        so = float(item.get('sonraki_olasilik', 0.2))
        sf = float(item.get('sonraki_frekans', 1))
        ss = float(item.get('sonraki_siddet', 1))
        next_score = so * sf * ss
        next_level = get_risk_level(next_score)
        
        # Önlemler listesini metne çevir
        onlemler = item.get('onlemler', '')
        if isinstance(onlemler, list):
            onlemler = '\n'.join([f"• {o}" for o in onlemler])
            
        row = [
            item.get('sira_no'), item.get('faaliyet_alani'), item.get('faaliyet_turu'),
            item.get('tehlike_tanimi'), item.get('risk_tanimi'),
            o, f, s, current_score, current_level["label"],
            onlemler, item.get('sorumlu'), item.get('sure'),
            so, sf, ss, next_score, next_level["label"]
        ]
        ws.append(row)
    
    # Hücre stilleri
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start=2):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(wrap_text=True, vertical='top')
        
        # Mevcut Risk Rengi
        score_cell = ws.cell(row=row_idx, column=9)
        try:
            val = float(score_cell.value)
            level = get_risk_level(val)
            score_cell.fill = PatternFill(start_color=level["color"], end_color=level["color"], fill_type="solid")
            if level["color"] in ["FF0070C0", "FF808080", "FFFF0000"]:
                score_cell.font = Font(color="FFFFFF", bold=True)
        except: pass
        
        # Sonraki Risk Rengi
        next_score_cell = ws.cell(row=row_idx, column=17)
        try:
            val = float(next_score_cell.value)
            level = get_risk_level(val)
            next_score_cell.fill = PatternFill(start_color=level["color"], end_color=level["color"], fill_type="solid")
        except: pass

    # Sütun genişlikleri
    widths = {'A': 8, 'B': 18, 'C': 18, 'D': 35, 'E': 30, 'J': 22, 'K': 50, 'L': 25, 'R': 22}
    for col, width in widths.items(): ws.column_dimensions[col].width = width
    
    return wb

def fetch_risks_in_batches(api_key, model_name, workplace, total_items=50, batch_size=10, progress_bar=None, status_text=None):
    all_risks = []
    
    # Gemini Ayarlari
    genai.configure(api_key=api_key)
    # Seçilen modeli kullan
    model = genai.GenerativeModel(model_name)
    
    num_batches = (total_items + batch_size - 1) // batch_size
    
    for i in range(num_batches):
        start_idx = i * batch_size + 1
        current_batch_size = min(batch_size, total_items - len(all_risks))
        
        if status_text:
            status_text.text(f"⏳ İşleniyor... Paket {i+1}/{num_batches} (Risk No: {start_idx}-{start_idx+current_batch_size-1})")
        if progress_bar:
            progress_bar.progress((i) / num_batches)
            
        prompt = f"""
        Sen uzman bir İSG (İş Sağlığı ve Güvenliği) mühendisisin.
        Görev: '{workplace}' işyeri/sektörü için {current_batch_size} adet detaylı risk değerlendirmesi yap.
        ÖNEMLİ: Bu bir serinin parçasıdır. Risk numaraları {start_idx}'den başlayarak {start_idx + current_batch_size - 1}'e kadar gitmeli.

        Fine Kinney Metodu değerleri:
        - Olasılık (O): 0.2, 0.5, 1, 3, 6, 10
        - Frekans (F): 0.5, 1, 2, 3, 6, 10
        - Şiddet (Ş): 1, 3, 7, 15, 40, 100
        
        Çıktı formatı: Sadece saf JSON array döndür. Markdown bloğu kullanma.
        Her obje şu anahtarları içermeli:
        - sira_no (Integer: {start_idx} - {start_idx + current_batch_size - 1})
        - faaliyet_alani (Örn: Genel Yönetim, Üretim Alanı)
        - faaliyet_turu (Örn: Çalışma Ortamı, Makine Kullanımı)
        - tehlike_tanimi (Detaylı tehlike açıklaması)
        - risk_tanimi (Olası etki: yaralanma, ölüm, maddi hasar)
        - olasilik (Fine Kinney değeri)
        - frekans (Fine Kinney değeri)
        - siddet (Fine Kinney değeri)
        - onlemler (DÖF - Düzeltici/Önleyici Faaliyetler, maddeler halinde)
        - sorumlu (Örn: İşveren & İSG Uzmanı)
        - sure (Aksiyon süresi: "Hemen", "1 Ay" vb.)
        - sonraki_olasilik (DÖF sonrası)
        - sonraki_frekans (DÖF sonrası)
        - sonraki_siddet (DÖF sonrası)
        
        KRİTİK KURALLAR:
        1. DÖF sonrası Risk Skoru (O×F×Ş) KESİNLİKLE 70 veya altında olmalı.
        2. "{workplace}" sektörüne özel gerçekçi riskler üret.
        3. En az 1 tane yüksek (400+) risk olsun.
        """
        
        try:
            # count_tokens ile maliyet kontrolü yapılabilir ama şimdilik direkt generate_content
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    response_mime_type="application/json"
                )
            )
            
            content = response.text.strip()
            # Bazı durumlarda yine de md block gelebilir
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            
            batch_data = json.loads(content)
            if isinstance(batch_data, dict): batch_data = [batch_data]
            all_risks.extend(batch_data)
            
            # Bellek Temizliği gerekmez ama yine de
            del content, response
            gc.collect()
            
        except Exception as e:
            st.error(f"Paket {i+1} Hatası: {str(e)}")
            time.sleep(2) # Hata durumunda bekle
            continue

    if progress_bar: progress_bar.progress(1.0)
    return all_risks

# === ARAYÜZ ===
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🛡️ İş Güvenliği Risk Analizi")
    st.markdown("İşyeri veya sektör adını girerek otomatik risk analizi oluşturun.")
with col2:
    st.image("isg_avatar.png", width=150)


# API Key Kontrolü
api_key = None

try:
    # Tüm olası key varyasyonlarını dene
    possible_keys = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "gemini_api_key", "google_api_key"]
    for k in possible_keys:
        if k in st.secrets:
            api_key = st.secrets[k]
            break
except Exception:
    pass

if not api_key:
    # Environment variable backup
    import os
    if os.getenv("GOOGLE_API_KEY"):
        api_key = os.getenv("GOOGLE_API_KEY")
    else:
        api_key = st.text_input("Google Gemini API Anahtarınızı Girin:", type="password")

if not api_key:
     st.warning("Devam etmek için Gemini API Key gereklidir.")
     st.stop()

# Varsayılan Model (Prefixsiz)
selected_model = "gemini-1.5-flash"

with st.form("risk_form"):
    workplace = st.text_input("İşyeri / Sektör Tanımı:", placeholder="Örn: Mobilya Atölyesi, Demir Çelik Fabrikası, İnşaat Şantiyesi...")
    risk_count = st.slider("Oluşturulacak Risk Sayısı:", min_value=10, max_value=100, value=50, step=10)
    submitted = st.form_submit_button("Analizi Oluştur 🚀")


if submitted:
    if not api_key:
        st.error("Lütfen API Anahtarını kontrol edin.")
    elif not workplace:
        st.error("Lütfen bir işyeri tanımı girin.")
    else:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            risks = fetch_risks_in_batches(api_key, selected_model, workplace, total_items=risk_count, batch_size=25, progress_bar=progress_bar, status_text=status_text)
            
            if risks:
                status_text.success(f"✅ {len(risks)} adet risk başarıyla analiz edildi!")
                
                # Excel Oluştur
                wb = create_excel(risks, workplace)
                output = io.BytesIO()
                wb.save(output)
                output.seek(0)
                
                # İndirme Butonu
                safe_name = "".join(c for c in workplace if c.isalnum() or c in (' ','-','_')).strip()
                st.download_button(
                    label="📥 Excel Dosyasını İndir",
                    data=output,
                    file_name=f"Risk_Analizi_{safe_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Önizleme (Opsiyonel)
                with st.expander("Sonuç Önizlemesi (İlk 5 Madde)"):
                    st.json(risks[:5])
                    
            else:
                st.error("Hiçbir risk verisi alınamadı. Lütfen tekrar deneyin.")
                
        except Exception as e:
            st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")

# Footer (Sabit Alt Bilgi)
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        Bu Uygulama İş Güvenliği Uzmanı(B) Fatih AKDENİZ tarafından geliştirilmiştir.
    </div>
    """,
    unsafe_allow_html=True
)
