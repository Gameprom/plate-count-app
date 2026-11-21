import streamlit as st
import cv2
import numpy as np
import pandas as pd

st.set_page_config(page_title="Standard Plate Count App", page_icon="🧫", layout="wide")
st.title("🧫 โปรแกรม Standard Plate Count (ช่วงมาตรฐาน 30 - 300 Colonies)")
st.write("ระบุชื่อเชื้อ อัปโหลดภาพจานเพาะเชื้อแยกตามระดับ Dilution (10⁻¹ ถึง 10⁻¹⁰) เพื่อนับจำนวนและคำนวณค่าเฉลี่ย CFU/mL")

# =================================================================
# แถบเมนูด้านข้าง (Sidebar)
# =================================================================
st.sidebar.header("🧪 1. ข้อมูลตัวอย่างและการทดลอง")
organism_name = st.sidebar.text_input("ชื่อเชื้อ / ชื่อตัวอย่าง (Sample Name)", value="E. coli (ตัวอย่างที่ 1)")
volume_ml = st.sidebar.number_input("ปริมาตรที่ลงเชื้อ (mL)", min_value=0.01, max_value=10.0, value=0.1, step=0.05)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. ตั้งค่าการตรวจจับภาพ")
shrink_factor = st.sidebar.slider("สัดส่วนขอบจานด้านใน", 0.85, 0.99, 0.945, 0.005)
margin = st.sidebar.slider("ระยะบีบขอบกันเส้นรบกวน (พิกเซล)", 0, 50, 28)
min_area = st.sidebar.slider("ขนาดพื้นที่เชื้อเล็กสุด (พิกเซล)", 1, 100, 5)
max_area = st.sidebar.slider("ขนาดพื้นที่เชื้อใหญ่สุด (พิกเซล)", 500, 5000, 1000)

# =================================================================
# ส่วนอัปโหลดรูปภาพแยกตามระดับ Dilution 10^-1 ถึง 10^-10
# =================================================================
st.subheader("📤 อัปโหลดภาพถ่ายจานเพาะเชื้อแยกตามระดับการเจือจาง (Dilution)")
st.caption("อัปโหลดเฉพาะระดับ Dilution ที่ต้องการนับ (อย่างละ 1 รูป) ช่องไหนไม่ได้ทำทดลองสามารถปล่อยว่างไว้ได้ครับ")

uploaded_dict = {}
# แบ่งช่องอัปโหลดเป็น 2 แถว แถวละ 5 คอลัมน์ (10^-1 ถึง 10^-10)
cols_row1 = st.columns(5)
for i in range(1, 6):
    with cols_row1[i - 1]:
        file = st.file_uploader(f"Dilution 10⁻{i}", type=["jpg", "jpeg", "png"], key=f"dil_{i}")
        if file is not None:
            uploaded_dict[i] = file

cols_row2 = st.columns(5)
for i in range(6, 11):
    with cols_row2[i - 6]:
        file = st.file_uploader(f"Dilution 10⁻{i}", type=["jpg", "jpeg", "png"], key=f"dil_{i}")
        if file is not None:
            uploaded_dict[i] = file

# =================================================================
# ส่วนประมวลผลภาพและคำนวณผลลัพธ์
# =================================================================
if uploaded_dict:
    st.markdown("---")
    summary_data = []
    processed_images = []
    valid_cfu_list = [] # เก็บค่า CFU/mL ของจานที่อยู่ในช่วง 30-300

    # วนลูปประมวลผลตามลำดับ Dilution จากน้อยไปมาก
    for dil_exp in sorted(uploaded_dict.keys()):
        uploaded_file = uploaded_dict[dil_exp]
        dilution_factor = 10 ** (-dil_exp)

        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, 1)
        output = image.copy()

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        height, width = gray.shape

        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=width // 2,
            param1=50, param2=30, minRadius=int(width * 0.3), maxRadius=int(width * 0.48)
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            center_x, center_y, outer_radius = circles[0, 0]
            inner_radius = int(outer_radius * shrink_factor)

            mask = np.zeros_like(gray)
            cv2.circle(mask, (center_x, center_y), inner_radius, 255, -1)
            roi_gray = cv2.bitwise_and(gray, gray, mask=mask)

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(roi_gray)

            blur_roi = cv2.GaussianBlur(enhanced, (5, 5), 0)
            thresh = cv2.adaptiveThreshold(
                blur_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 25, 6
            )
            
            mask_eroded = np.zeros_like(gray)
            cv2.circle(mask_eroded, (center_x, center_y), inner_radius - margin, 255, -1)
            clean_thresh = cv2.bitwise_and(thresh, thresh, mask=mask_eroded)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            closed = cv2.morphologyEx(clean_thresh, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            colony_count = 0
            cv2.circle(output, (center_x, center_y), inner_radius - margin, (255, 200, 0), 2)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area < area < max_area:
                    colony_count += 1
                    (x, y), radius = cv2.minEnclosingCircle(cnt)
                    center = (int(x), int(y))
                    radius = int(radius) + 3
                    
                    cv2.circle(output, center, radius, (0, 255, 0), 2)
                    cv2.putText(output, str(colony_count), (int(x) - 10, int(y) - radius - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # คำนวณ CFU/mL ของจานนี้
            cfu_per_ml = colony_count / (dilution_factor * volume_ml)

            # ตรวจสอบเกณฑ์มาตรฐาน 30 - 300 Colonies
            if 30 <= colony_count <= 300:
                status = "✅ อยู่ในเกณฑ์ (30-300)"
                valid_cfu_list.append(cfu_per_ml)
            elif colony_count < 30:
                status = "⚠️ น้อยกว่า 30 (TFTC)"
            else:
                status = "⚠️ มากกว่า 300 (TNTC)"

            summary_data.append({
                "ชื่อเชื้อ/ตัวอย่าง": organism_name,
                "ระดับ Dilution": f"10^-{dil_exp}",
                "จำนวน Colony": colony_count,
                "เกณฑ์มาตรฐาน (30-300)": status,
                "CFU/mL": f"{cfu_per_ml:,.0f}",
                "CFU/mL (วิทย์)": f"{cfu_per_ml:.2e}"
            })

            output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            _, img_encoded = cv2.imencode('.jpg', output)
            processed_images.append((dil_exp, uploaded_file.name, colony_count, status, cfu_per_ml, output_rgb, img_encoded.tobytes()))
        else:
            summary_data.append({
                "ชื่อเชื้อ/ตัวอย่าง": organism_name,
                "ระดับ Dilution": f"10^-{dil_exp}",
                "จำนวน Colony": "ไม่พบขอบจาน",
                "เกณฑ์มาตรฐาน (30-300)": "❌ ตรวจสอบภาพ",
                "CFU/mL": "-",
                "CFU/mL (วิทย์)": "-"
            })

    # =================================================================
    # แสดงผลสรุปค่าเฉลี่ย CFU/mL (เฉพาะช่วง 30 - 300 Colonies)
    # =================================================================
    st.subheader(f"📋 สรุปผลการวิเคราะห์เชื้อ: {organism_name}")
    
    if valid_cfu_list:
        avg_cfu = sum(valid_cfu_list) / len(valid_cfu_list)
        st.success(
            f"### 🎯 ค่าเฉลี่ยปริมาณเชื้อ (ช่วง 30 - 300 Colonies): **{avg_cfu:,.0f} CFU/mL** ({avg_cfu:.2e} CFU/mL)\n"
            f"*(คำนวณเฉลี่ยจากจานที่ผ่านเกณฑ์จำนวน {len(valid_cfu_list)} Dilution)*"
        )
    else:
        st.warning("⚠️ **ยังไม่มีจานเพาะเชื้อที่อยู่ในเกณฑ์มาตรฐาน 30 - 300 Colonies** (ระบบจึงยังไม่สามารถคำนวณค่าเฉลี่ยมาตรฐานได้ กรุณาตรวจสอบตารางด้านล่าง)")

    # แสดงตารางผลลัพธ์ทั้งหมด
    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True)

    # ปุ่มดาวน์โหลด CSV
    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label=f"📥 ดาวน์โหลดผลลัพธ์ของ {organism_name} (ไฟล์ CSV / Excel)",
        data=csv_data,
        file_name=f"plate_count_{organism_name.replace(' ', '_')}.csv",
        mime="text/csv"
    )

    # =================================================================
    # แสดงภาพผลการนับราย Dilution
    # =================================================================
    st.markdown("---")
    st.subheader("🖼️ ภาพผลการนับเชื้อแต่ละ Dilution")
    
    img_cols = st.columns(3) # แสดงแถวละ 3 ภาพเพื่อให้ดูเทียบกันได้ง่าย
    for idx, (dil_exp, filename, count, status, cfu, img_rgb, img_bytes) in enumerate(processed_images):
        with img_cols[idx % 3]:
            st.markdown(f"**Dilution 10⁻{dil_exp}** | นับได้ **{count}** Colonies")
            st.caption(f"สถานะ: {status} | {cfu:.2e} CFU/mL")
            st.image(img_rgb, use_container_width=True)
            st.download_button(
                label=f"💾 โหลดภาพ 10⁻{dil_exp}",
                data=img_bytes,
                file_name=f"counted_10-{dil_exp}_{filename}",
                mime="image/jpeg",
                key=f"dl_{dil_exp}"
            )
