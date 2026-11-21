import streamlit as st
import cv2
import numpy as np
import pandas as pd
import base64
from datetime import datetime

st.set_page_config(page_title="Standard Plate Count App", page_icon="🧫", layout="wide")
st.title("🧫 โปรแกรม Standard Plate Count (ช่วงมาตรฐาน 30 - 300 Colonies)")
st.write("ระบุชื่อเชื้อ อัปโหลดภาพจานเพาะเชื้อแยกตามระดับ Dilution (10⁻¹ ถึง 10⁻¹⁰) เพื่อนับจำนวน คำนวณค่าเฉลี่ย และออกรายงาน")

# =================================================================
# แถบเมนูด้านข้าง (Sidebar)
# =================================================================
st.sidebar.header("🧪 1. ข้อมูลตัวอย่างและการทดลอง")
organism_name = st.sidebar.text_input("ชื่อเชื้อ / ชื่อตัวอย่าง (Sample Name)", value="E. coli (ตัวอย่างที่ 1)")
tester_name = st.sidebar.text_input("ผู้ทำการทดสอบ (Analyst)", value="เจ้าหน้าที่ห้องปฏิบัติการ")
volume_ml = st.sidebar.number_input("ปริมาตรที่ลงเชื้อ (mL)", min_value=0.01, max_value=10.0, value=0.1, step=0.05)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. ตั้งค่าการตรวจจับภาพ")
shrink_factor = st.sidebar.slider("สัดส่วนขอบจานด้านใน", 0.85, 0.99, 0.945, 0.005)
margin = st.sidebar.slider("ระยะบีบขอบกันเส้นรบกวน (พิกเซล)", 0, 50, 28)
min_area = st.sidebar.slider("ขนาดพื้นที่เชื้อเล็กสุด (พิกเซล)", 1, 100, 5)
max_area = st.sidebar.slider("ขนาดพื้นที่เชื้อใหญ่สุด (พิกเซล)", 500, 5000, 1000)

st.sidebar.markdown("---")
st.sidebar.header("🔬 3. แยกจุดติดกัน (Watershed)")
watershed_dist = st.sidebar.slider(
    "ความไวในการแยกจุดติดกัน (0 = ปิด)", 
    min_value=0.0, max_value=0.8, value=0.45, step=0.05,
    help="ยิ่งค่าสูง ยิ่งแยกจุดที่ติดกันได้ละเอียดขึ้น (แนะนำ 0.40 - 0.55 หากจุดเล็กๆ ถูกแบ่งเกินให้ลดค่าลง)"
)

# =================================================================
# ส่วนอัปโหลดรูปภาพแยกตามระดับ Dilution 10^-1 ถึง 10^-10
# =================================================================
st.subheader("📤 อัปโหลดภาพถ่ายจานเพาะเชื้อแยกตามระดับการเจือจาง (Dilution)")
st.caption("อัปโหลดเฉพาะระดับ Dilution ที่ต้องการนับ (อย่างละ 1 รูป) ช่องไหนไม่ได้ทำทดลองสามารถปล่อยว่างไว้ได้ครับ")

uploaded_dict = {}
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
# ฟังก์ชันสร้างไฟล์รายงาน HTML
# =================================================================
def generate_html_report(org_name, analyst, vol, avg_text, df_table, img_list):
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    table_html = df_table.to_html(index=False, border=1, classes="report-table")
    
    images_html = ""
    for dil_exp, filename, count, status, cfu, _, img_bytes in img_list:
        b64_img = base64.b64encode(img_bytes).decode('utf-8')
        images_html += f"""
        <div class="img-card">
            <h4>Dilution 10<sup>-{dil_exp}</sup> ({filename})</h4>
            <p><strong>นับได้:</strong> {count} Colonies | <strong>CFU/mL:</strong> {cfu:.2e}</p>
            <p><strong>สถานะ:</strong> {status}</p>
            <img src="data:image/jpeg;base64,{b64_img}" alt="Dilution 10-{dil_exp}">
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>รายงานผลการวิเคราะห์ Plate Count - {org_name}</title>
        <style>
            body {{ font-family: 'Sarabun', 'Tahoma', sans-serif; margin: 30px; color: #222; }}
            .header {{ border-bottom: 2px solid #2c3e50; padding-bottom: 15px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #1a5276; font-size: 24px; }}
            .meta-info {{ display: flex; justify-content: space-between; margin-top: 10px; font-size: 14px; color: #555; }}
            .summary-box {{ background-color: #eafaf1; border-left: 5px solid #2ecc71; padding: 15px; margin-bottom: 25px; font-size: 16px; }}
            .report-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 14px; }}
            .report-table th {{ background-color: #2c3e50; color: white; padding: 10px; text-align: center; }}
            .report-table td {{ padding: 8px; text-align: center; border: 1px solid #ddd; }}
            .report-table tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .img-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
            .img-card {{ border: 1px solid #ccc; border-radius: 8px; padding: 12px; text-align: center; page-break-inside: avoid; }}
            .img-card h4 {{ margin: 5px 0; color: #1a5276; }}
            .img-card p {{ margin: 4px 0; font-size: 13px; }}
            .img-card img {{ max-width: 100%; height: auto; border-radius: 4px; margin-top: 8px; }}
            @media print {{
                body {{ margin: 10mm; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print" style="background:#fff3cd; padding:10px; margin-bottom:20px; border-radius:5px; text-align:center;">
            💡 <strong>คำแนะนำ:</strong> กดปุ่ม <strong>Ctrl + P</strong> (หรือ Command + P) เพื่อบันทึกเอกสารนี้เป็นไฟล์ <strong>PDF</strong> ได้ทันที
        </div>
        <div class="header">
            <h1>รายงานผลการวิเคราะห์ปริมาณจุลินทรีย์ (Standard Plate Count Report)</h1>
            <div class="meta-info">
                <div><strong>ชื่อเชื้อ / ตัวอย่าง:</strong> {org_name} &nbsp;|&nbsp; <strong>ปริมาตรที่ลงเชื้อ:</strong> {vol} mL</div>
                <div><strong>ผู้ทดสอบ:</strong> {analyst} &nbsp;|&nbsp; <strong>วันที่ออกรายงาน:</strong> {now_str}</div>
            </div>
        </div>
        <div class="summary-box">{avg_text}</div>
        <h3>1. ตารางสรุปผลการนับ Colony รายระดับการเจือจาง</h3>
        {table_html}
        <h3>2. ภาพถ่ายจานเพาะเชื้อและตำแหน่งการตรวจจับ</h3>
        <div class="img-grid">{images_html}</div>
    </body>
    </html>
    """
    return html_content.encode('utf-8')

# =================================================================
# ส่วนประมวลผลภาพและคำนวณผลลัพธ์ (อัปเกรด Watershed)
# =================================================================
if uploaded_dict:
    st.markdown("---")
    summary_data = []
    processed_images = []
    valid_cfu_list = []

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

            # -------------------------------------------------------------
            # ขั้นตอนใหม่: Watershed Algorithm สำหรับแยกจุด Colony ที่ติดกัน
            # -------------------------------------------------------------
            if watershed_dist > 0:
                # 1. หาพื้นที่พื้นหลังที่แน่นอน (Sure Background)
                sure_bg = cv2.dilate(closed, kernel, iterations=2)
                
                # 2. หาจุดศูนย์กลางของเชื้อแต่ละก้อน (Distance Transform)
                dist_transform = cv2.distanceTransform(closed, cv2.DIST_L2, 5)
                if dist_transform.max() > 0:
                    _, sure_fg = cv2.threshold(dist_transform, watershed_dist * dist_transform.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    
                    # 3. หาบริเวณรอยต่อที่ไม่แน่ใจ (Unknown region)
                    unknown = cv2.subtract(sure_bg, sure_fg)
                    
                    # 4. ติดป้ายกำกับยอดเขาแต่ละจุด (Markers)
                    _, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[unknown == 255] = 0
                    
                    # 5. รัน Watershed เพื่อสร้างเส้นแบ่งเขตระหว่างจุดที่ติดกัน
                    img_for_ws = cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)
                    markers = cv2.watershed(img_for_ws, markers)
                    
                    # สร้างภาพขาวดำใหม่ที่ถูกผ่าแบ่งเส้นรอยต่อแล้ว (เส้นแบ่งมีค่า -1)
                    separated = closed.copy()
                    separated[markers == -1] = 0
                else:
                    separated = closed
            else:
                separated = closed

            # ค้นหา Contours จากภาพที่ผ่านการแยกจุดติดกันแล้ว
            contours, _ = cv2.findContours(separated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
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

            cfu_per_ml = colony_count / (dilution_factor * volume_ml)

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
    # แสดงผลสรุปค่าเฉลี่ย CFU/mL และปุ่มดาวน์โหลดรายงาน
    # =================================================================
    st.subheader(f"📋 สรุปผลการวิเคราะห์เชื้อ: {organism_name}")
    
    if valid_cfu_list:
        avg_cfu = sum(valid_cfu_list) / len(valid_cfu_list)
        report_avg_html = f"<strong>ค่าเฉลี่ยปริมาณเชื้อ (ช่วง 30 - 300 Colonies):</strong> {avg_cfu:,.0f} CFU/mL ({avg_cfu:.2e} CFU/mL) — <em>คำนวณจาก {len(valid_cfu_list)} Dilution ที่ผ่านเกณฑ์</em>"
        st.success(
            f"### 🎯 ค่าเฉลี่ยปริมาณเชื้อ (ช่วง 30 - 300 Colonies): **{avg_cfu:,.0f} CFU/mL** ({avg_cfu:.2e} CFU/mL)\n"
            f"*(คำนวณเฉลี่ยจากจานที่ผ่านเกณฑ์จำนวน {len(valid_cfu_list)} Dilution)*"
        )
    else:
        report_avg_html = "<strong>หมายเหตุ:</strong> ยังไม่มีจานเพาะเชื้อที่อยู่ในเกณฑ์มาตรฐาน 30 - 300 Colonies"
        st.warning("⚠️ **ยังไม่มีจานเพาะเชื้อที่อยู่ในเกณฑ์มาตรฐาน 30 - 300 Colonies** (ระบบจึงยังไม่สามารถคำนวณค่าเฉลี่ยมาตรฐานได้ กรุณาตรวจสอบตารางด้านล่าง)")

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True)

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        report_bytes = generate_html_report(organism_name, tester_name, volume_ml, report_avg_html, df, processed_images)
        st.download_button(
            label="📄 ดาวน์โหลดรายงานฉบับเต็ม (ตาราง + รูปภาพ / พิมพ์เป็น PDF ได้)",
            data=report_bytes,
            file_name=f"Report_{organism_name.replace(' ', '_')}.html",
            mime="text/html",
            use_container_width=True
        )
    with dl_col2:
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📊 ดาวน์โหลดเฉพาะตารางข้อมูล (ไฟล์ CSV / Excel)",
            data=csv_data,
            file_name=f"Data_{organism_name.replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("---")
    st.subheader("🖼️ ภาพผลการนับเชื้อแต่ละ Dilution")
    
    img_cols = st.columns(3)
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
