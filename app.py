import streamlit as st
import cv2
import numpy as np
import pandas as pd
import base64
from datetime import datetime
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Standard Plate Count App", page_icon="🧫", layout="wide")
st.title("🧫 โปรแกรม Standard Plate Count (ช่วงมาตรฐาน 30 - 300 Colonies)")
st.write("ระบุชื่อเชื้อ อัปโหลดภาพจานเพาะเชื้อแยกตามระดับ Dilution (10⁻¹ ถึง 10⁻¹⁰) พร้อมระบบซูมขยายและคลิกแก้ไขจุดนับ")

# สร้างตัวแปรหน่วยความจำ (Session State)
if "manual_adds" not in st.session_state:
    st.session_state.manual_adds = {}
if "manual_removes" not in st.session_state:
    st.session_state.manual_removes = {}
if "last_click" not in st.session_state:
    st.session_state.last_click = {}

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
    min_value=0.0, max_value=0.8, value=0.45, step=0.05
)

st.sidebar.markdown("---")
st.sidebar.header("🎨 4. การแสดงผลบนภาพ")
show_numbers = st.sidebar.checkbox("แสดงตัวเลขกำกับบนจุดเชื้อ", value=True)

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
        <h3>2. ภาพถ่ายจานเพาะเชื้อและตำแหน่งการตรวจจับ (🟢 อัตโนมัติ / 🔵 เพิ่มด้วยมือ)</h3>
        <div class="img-grid">{images_html}</div>
    </body>
    </html>
    """
    return html_content.encode('utf-8')

# =================================================================
# ส่วนประมวลผลภาพ + ระบบคลิกแก้ไขด้วยมือ
# =================================================================
if uploaded_dict:
    st.markdown("---")
    summary_data = []
    processed_images = []
    valid_cfu_list = []

    for dil_exp in sorted(uploaded_dict.keys()):
        uploaded_file = uploaded_dict[dil_exp]
        dilution_factor = 10 ** (-dil_exp)

        if dil_exp not in st.session_state.manual_adds:
            st.session_state.manual_adds[dil_exp] = []
        if dil_exp not in st.session_state.manual_removes:
            st.session_state.manual_removes[dil_exp] = []

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

            if watershed_dist > 0:
                sure_bg = cv2.dilate(closed, kernel, iterations=2)
                dist_transform = cv2.distanceTransform(closed, cv2.DIST_L2, 5)
                if dist_transform.max() > 0:
                    _, sure_fg = cv2.threshold(dist_transform, watershed_dist * dist_transform.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    unknown = cv2.subtract(sure_bg, sure_fg)
                    _, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[unknown == 255] = 0
                    img_for_ws = cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)
                    markers = cv2.watershed(img_for_ws, markers)
                    separated = closed.copy()
                    separated[markers == -1] = 0
                else:
                    separated = closed
            else:
                separated = closed

            contours, _ = cv2.findContours(separated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            auto_points = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area < area < max_area:
                    (x, y), radius = cv2.minEnclosingCircle(cnt)
                    is_removed = any(np.hypot(x - rx, y - ry) < 20 for (rx, ry) in st.session_state.manual_removes[dil_exp])
                    if not is_removed:
                        auto_points.append((int(x), int(y), int(radius) + 3, "auto"))

            all_points = auto_points + [(ax, ay, 10, "manual") for (ax, ay) in st.session_state.manual_adds[dil_exp]]

            cv2.circle(output, (center_x, center_y), inner_radius - margin, (255, 200, 0), 2)

            colony_count = 0
            for (px, py, pr, ptype) in all_points:
                colony_count += 1
                color = (0, 255, 0) if ptype == "auto" else (255, 180, 0)
                cv2.circle(output, (px, py), pr, color, 2)
                if show_numbers:
                    cv2.putText(output, str(colony_count), (px - 8, py - pr - 3),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

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

    # =================================================================
    # ส่วนตรวจสอบภาพแบบซูมขยายได้ + คลิกแก้ไขจุดนับด้วยมือ
    # =================================================================
    if processed_images:
        st.markdown("---")
        st.subheader("🔍 ตรวจสอบภาพแบบขยายใหญ่ และคลิกแก้ไขจุดนับด้วยมือ")
        
        dil_options = {f"Dilution 10⁻{item[0]} ({item[1]}) — นับได้ {item[2]} Colonies": idx for idx, item in enumerate(processed_images)}
        selected_label = st.selectbox("เลือกจานเพาะเชื้อที่ต้องการตรวจสอบ:", list(dil_options.keys()))
        selected_idx = dil_options[selected_label]
        
        dil_exp, filename, count, status, cfu, img_rgb, img_bytes = processed_images[selected_idx]

        c_col1, c_col2 = st.columns([1.2, 1])
        with c_col1:
            click_mode = st.radio(
                "โหมดเมื่อคลิกซ้ายบนภาพ:",
                ["➕ เพิ่มจุด Colony (วงสีฟ้า)", "➖ ลบจุดที่นับเกิน / ฝุ่น"],
                horizontal=True
            )
        with c_col2:
            zoom_size = st.select_slider(
                "🔍 ปรับขนาดความกว้างภาพ (พิกเซล) เพื่อซูมดูจุดเล็ก:",
                options=[700, 1000, 1400, 1800, 2200],
                value=1000
            )

        st.info("💡 **วิธีเลื่อนดูภาพเมื่อขยายใหญ่:** ใช้แถบเลื่อน (Scrollbar) ด้านล่าง/ด้านข้าง หรือกด **Shift + หมุนลูกกลิ้งเมาส์** เพื่อเลื่อนซ้าย-ขวา และคลิกซ้ายเพื่อเพิ่ม/ลบจุดได้ทันที")
        st.markdown(f"**กำลังแสดงผล:** Dilution 10⁻{dil_exp} | นับได้ **{count}** Colonies ({status}) | ความกว้างภาพ **{zoom_size} px**")
        
        pil_img = Image.fromarray(img_rgb)
        orig_w, orig_h = pil_img.size
        scale = orig_w / zoom_size

        # แสดงภาพผ่าน streamlit_image_coordinates ตามขนาดที่เลือกซูม (ขึ้นภาพ 100% ไม่ติดบล็อก)
        coords = streamlit_image_coordinates(pil_img, width=zoom_size, key=f"img_zoom_{dil_exp}_{zoom_size}")

        if coords is not None:
            click_tuple = (coords["x"], coords["y"], zoom_size)
            if st.session_state.last_click.get(dil_exp) != click_tuple:
                st.session_state.last_click[dil_exp] = click_tuple
                real_x = int(coords["x"] * scale)
                real_y = int(coords["y"] * scale)

                if "เพิ่มจุด" in click_mode:
                    st.session_state.manual_adds[dil_exp].append((real_x, real_y))
                else:
                    matched_add = [p for p in st.session_state.manual_adds[dil_exp] if np.hypot(real_x - p[0], real_y - p[1]) < 25]
                    if matched_add:
                        st.session_state.manual_adds[dil_exp].remove(matched_add[0])
                    else:
                        st.session_state.manual_removes[dil_exp].append((real_x, real_y))
                st.rerun()

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button(f"🔄 รีเซ็ตการแก้ไขทั้งหมดของ Dilution 10⁻{dil_exp}", use_container_width=True):
                st.session_state.manual_adds[dil_exp] = []
                st.session_state.manual_removes[dil_exp] = []
                st.session_state.last_click[dil_exp] = None
                st.rerun()
        with b_col2:
            st.download_button(
                label=f"💾 ดาวน์โหลดภาพผลลัพธ์เต็มใบ (Dilution 10⁻{dil_exp})",
                data=img_bytes,
                file_name=f"counted_10-{dil_exp}_{filename}",
                mime="image/jpeg",
                use_container_width=True
            )
