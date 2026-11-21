import streamlit as st
import cv2
import numpy as np

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Plate Count Web App", page_icon="🧫")
st.title("🧫 โปรแกรม Plate Count นับ Colony เชื้อ")
st.write("อัปโหลดภาพถ่ายจานเพาะเชื้อ เพื่อนับจำนวน Colony อัตโนมัติ")

# แถบเมนูด้านข้าง ตั้งค่าเริ่มต้นตามที่คุณปรับจูนจนพอใจแล้ว
st.sidebar.header("⚙️ ตั้งค่าการตรวจจับ")
shrink_factor = st.sidebar.slider("สัดส่วนขอบจานด้านใน", 0.85, 0.99, 0.945, 0.005)
margin = st.sidebar.slider("ระยะบีบขอบกันเส้นรบกวน (พิกเซล)", 0, 50, 28)
min_area = st.sidebar.slider("ขนาดพื้นที่เชื้อเล็กสุด (พิกเซล)", 1, 100, 5)
max_area = st.sidebar.slider("ขนาดพื้นที่เชื้อใหญ่สุด (พิกเซล)", 500, 5000, 1000)

# ปุ่มอัปโหลดรูปภาพ
uploaded_file = st.file_uploader("เลือกรูปภาพจานเพาะเชื้อ (JPG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # แปลงไฟล์ภาพที่อัปโหลดให้ OpenCV อ่านได้ (แทนที่คำสั่ง cv2.imread)
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, 1)
    output = image.copy()

    # =================================================================
    # ส่วนประมวลผลภาพ (ยกมาจากโค้ดที่คุณปรับจูนจนพอใจทั้งหมด)
    # =================================================================
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

        # วาดเส้นขอบเขตพื้นที่นับสีฟ้าอ่อนไว้ดูเป็นแนวอ้างอิง
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

        # =================================================================
        # ส่วนแสดงผลลัพธ์บนหน้าเว็บ (แทนที่คำสั่ง print และ cv2_imshow)
        # =================================================================
        st.success(f"### สรุปผลการนับ: พบทั้งหมด {colony_count} Colonies")
        
        # แปลงสีจาก BGR เป็น RGB เพื่อให้แสดงผลบนเว็บได้สีตรงตามจริง
        output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        st.image(output_rgb, caption="ภาพผลลัพธ์การนับ Colony", use_container_width=True)
    else:
        st.error("ไม่พบขอบจานเพาะเชื้อ กรุณาตรวจสอบรูปภาพอีกครั้ง")
