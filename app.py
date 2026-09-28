import streamlit as st
import sqlite3
from datetime import datetime, date
from pathlib import Path
import pandas as pd

# ============================================================
# CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="Hotel Manager",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = Path("hotel_manager.db")


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            floor INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Trống'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            id_number TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            adults INTEGER DEFAULT 1,
            children INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Đã đặt',
            total_amount REAL DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guest_id) REFERENCES guests(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT DEFAULT 'Tiền mặt',
            payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
            note TEXT,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        )
    """)

    # Tạo dữ liệu phòng mẫu nếu database chưa có phòng
    cursor.execute("SELECT COUNT(*) AS total FROM rooms")
    count = cursor.fetchone()["total"]

    if count == 0:
        sample_rooms = [
            ("101", "Deluxe", 1, 1800000, "Trống"),
            ("102", "Deluxe", 1, 1800000, "Trống"),
            ("103", "Deluxe", 1, 1800000, "Trống"),
            ("104", "Superior", 1, 1500000, "Trống"),
            ("201", "Deluxe", 2, 2000000, "Trống"),
            ("202", "Deluxe", 2, 2000000, "Trống"),
            ("203", "Suite", 2, 3500000, "Trống"),
            ("204", "Suite", 2, 3500000, "Trống"),
            ("301", "Deluxe", 3, 2200000, "Trống"),
            ("302", "Deluxe", 3, 2200000, "Trống"),
            ("303", "Suite", 3, 4000000, "Trống"),
            ("304", "VIP", 3, 5500000, "Trống"),
        ]

        cursor.executemany("""
            INSERT INTO rooms
            (room_number, room_type, floor, price, status)
            VALUES (?, ?, ?, ?, ?)
        """, sample_rooms)

    conn.commit()
    conn.close()


# ============================================================
# HÀM DATABASE
# ============================================================

def fetch_rooms():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM rooms ORDER BY floor, room_number",
        conn
    )
    conn.close()
    return df


def fetch_bookings():
    conn = get_connection()

    query = """
        SELECT
            b.id,
            g.full_name,
            g.phone,
            r.room_number,
            r.room_type,
            b.check_in,
            b.check_out,
            b.adults,
            b.children,
            b.status,
            b.total_amount,
            b.note
        FROM bookings b
        JOIN guests g ON b.guest_id = g.id
        JOIN rooms r ON b.room_id = r.id
        ORDER BY b.id DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def add_room(room_number, room_type, floor, price):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO rooms
            (room_number, room_type, floor, price, status)
            VALUES (?, ?, ?, ?, 'Trống')
        """, (room_number, room_type, floor, price))

        conn.commit()
        return True, "Thêm phòng thành công."

    except sqlite3.IntegrityError:
        return False, "Số phòng đã tồn tại."

    finally:
        conn.close()


def update_room(room_id, room_number, room_type, floor, price, status):
    conn = get_connection()

    try:
        conn.execute("""
            UPDATE rooms
            SET room_number = ?,
                room_type = ?,
                floor = ?,
                price = ?,
                status = ?
            WHERE id = ?
        """, (
            room_number,
            room_type,
            floor,
            price,
            status,
            room_id
        ))

        conn.commit()
        return True, "Cập nhật phòng thành công."

    except sqlite3.IntegrityError:
        return False, "Số phòng đã tồn tại."

    finally:
        conn.close()


def delete_room(room_id):
    conn = get_connection()

    booking_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE room_id = ?",
        (room_id,)
    ).fetchone()[0]

    if booking_count > 0:
        conn.close()
        return False, "Không thể xóa phòng vì phòng đã có lịch sử đặt."

    conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    conn.commit()
    conn.close()

    return True, "Đã xóa phòng."


def create_booking(
    full_name,
    phone,
    email,
    id_number,
    room_id,
    check_in,
    check_out,
    adults,
    children,
    note
):
    conn = get_connection()

    try:
        # Tạo khách
        cursor = conn.execute("""
            INSERT INTO guests
            (full_name, phone, email, id_number)
            VALUES (?, ?, ?, ?)
        """, (
            full_name,
            phone,
            email,
            id_number
        ))

        guest_id = cursor.lastrowid

        # Lấy giá phòng
        room = conn.execute(
            "SELECT price FROM rooms WHERE id = ?",
            (room_id,)
        ).fetchone()

        if not room:
            raise ValueError("Không tìm thấy phòng.")

        price = room["price"]

        nights = (check_out - check_in).days

        if nights <= 0:
            raise ValueError("Ngày trả phòng phải sau ngày nhận phòng.")

        total = nights * price

        conn.execute("""
            INSERT INTO bookings
            (
                guest_id,
                room_id,
                check_in,
                check_out,
                adults,
                children,
                status,
                total_amount,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            guest_id,
            room_id,
            check_in.isoformat(),
            check_out.isoformat(),
            adults,
            children,
            "Đã đặt",
            total,
            note
        ))

        conn.execute("""
            UPDATE rooms
            SET status = 'Đã đặt'
            WHERE id = ?
        """, (room_id,))

        conn.commit()

        return True, f"Đặt phòng thành công. Tổng tiền: {total:,.0f} VNĐ"

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


def update_booking_status(booking_id, new_status):
    conn = get_connection()

    booking = conn.execute("""
        SELECT room_id
        FROM bookings
        WHERE id = ?
    """, (booking_id,)).fetchone()

    if not booking:
        conn.close()
        return False, "Không tìm thấy booking."

    room_id = booking["room_id"]

    conn.execute("""
        UPDATE bookings
        SET status = ?
        WHERE id = ?
    """, (new_status, booking_id))

    if new_status == "Đã đặt":
        room_status = "Đã đặt"

    elif new_status == "Đang ở":
        room_status = "Đang ở"

    elif new_status == "Đã trả phòng":
        room_status = "Đang dọn"

    elif new_status == "Hủy":
        room_status = "Trống"

    else:
        room_status = "Trống"

    conn.execute("""
        UPDATE rooms
        SET status = ?
        WHERE id = ?
    """, (room_status, room_id))

    conn.commit()
    conn.close()

    return True, "Đã cập nhật trạng thái."


def make_payment(booking_id, amount, method, note):
    conn = get_connection()

    conn.execute("""
        INSERT INTO payments
        (booking_id, amount, payment_method, note)
        VALUES (?, ?, ?, ?)
    """, (
        booking_id,
        amount,
        method,
        note
    ))

    conn.commit()
    conn.close()


# ============================================================
# HÀM HIỂN THỊ
# ============================================================

def format_money(value):
    return f"{value:,.0f} VNĐ"


def status_color(status):
    mapping = {
        "Trống": "🟢",
        "Đã đặt": "🟡",
        "Đang ở": "🔵",
        "Đang dọn": "🟠",
        "Bảo trì": "🔴"
    }

    return mapping.get(status, "⚪")


# ============================================================
# KHỞI TẠO
# ============================================================

init_database()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏨 HOTEL MANAGER")
st.sidebar.caption("Hệ thống quản lý khách sạn")

menu = st.sidebar.radio(
    "MENU",
    [
        "📊 Tổng quan",
        "🛏️ Quản lý phòng",
        "📅 Đặt phòng",
        "👤 Khách lưu trú",
        "💳 Thanh toán"
    ]
)

st.sidebar.divider()

st.sidebar.info(
    "Phần mềm quản lý phòng khách sạn "
    "được xây dựng bằng Streamlit + SQLite."
)


# ============================================================
# TỔNG QUAN
# ============================================================

if menu == "📊 Tổng quan":

    st.title("📊 Tổng quan khách sạn")
    st.caption(
        f"Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    rooms = fetch_rooms()
    bookings = fetch_bookings()

    total_rooms = len(rooms)

    empty_rooms = len(
        rooms[rooms["status"] == "Trống"]
    )

    reserved_rooms = len(
        rooms[rooms["status"] == "Đã đặt"]
    )

    occupied_rooms = len(
        rooms[rooms["status"] == "Đang ở"]
    )

    cleaning_rooms = len(
        rooms[rooms["status"] == "Đang dọn"]
    )

    maintenance_rooms = len(
        rooms[rooms["status"] == "Bảo trì"]
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    col1.metric("Tổng phòng", total_rooms)
    col2.metric("🟢 Trống", empty_rooms)
    col3.metric("🟡 Đã đặt", reserved_rooms)
    col4.metric("🔵 Đang ở", occupied_rooms)
    col5.metric("🟠 Đang dọn", cleaning_rooms)
    col6.metric("🔴 Bảo trì", maintenance_rooms)

    st.divider()

    st.subheader("🏨 Sơ đồ phòng")

    if not rooms.empty:

        floors = sorted(rooms["floor"].unique())

        for floor in floors:

            st.markdown(f"### Tầng {floor}")

            floor_rooms = rooms[
                rooms["floor"] == floor
            ]

            columns = st.columns(4)

            for index, (_, room) in enumerate(
                floor_rooms.iterrows()
            ):

                with columns[index % 4]:

                    st.markdown(
                        f"""
                        <div style="
                            border:1px solid #ddd;
                            border-radius:10px;
                            padding:15px;
                            margin-bottom:10px;
                            background:#fafafa;
                        ">
                            <h3>🚪 {room['room_number']}</h3>
                            <p>{room['room_type']}</p>
                            <p>{status_color(room['status'])}
                            <b>{room['status']}</b></p>
                            <p>{format_money(room['price'])}/đêm</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    st.divider()

    st.subheader("📅 Đặt phòng gần đây")

    if bookings.empty:
        st.info("Chưa có dữ liệu đặt phòng.")
    else:
        st.dataframe(
            bookings.head(10),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# QUẢN LÝ PHÒNG
# ============================================================

elif menu == "🛏️ Quản lý phòng":

    st.title("🛏️ Quản lý phòng")

    tab1, tab2, tab3 = st.tabs(
        [
            "Danh sách phòng",
            "Thêm phòng",
            "Chỉnh sửa phòng"
        ]
    )

    rooms = fetch_rooms()

    # --------------------------------------------------------
    # DANH SÁCH
    # --------------------------------------------------------

    with tab1:

        col1, col2 = st.columns(2)

        with col1:
            search = st.text_input(
                "🔎 Tìm số phòng",
                placeholder="Ví dụ: 101"
            )

        with col2:
            status_filter = st.selectbox(
                "Lọc trạng thái",
                [
                    "Tất cả",
                    "Trống",
                    "Đã đặt",
                    "Đang ở",
                    "Đang dọn",
                    "Bảo trì"
                ]
            )

        filtered = rooms.copy()

        if search:
            filtered = filtered[
                filtered["room_number"]
                .astype(str)
                .str.contains(search, case=False)
            ]

        if status_filter != "Tất cả":
            filtered = filtered[
                filtered["status"] == status_filter
            ]

        st.dataframe(
            filtered[
                [
                    "id",
                    "room_number",
                    "room_type",
                    "floor",
                    "price",
                    "status"
                ]
            ],
            column_config={
                "id": "ID",
                "room_number": "Số phòng",
                "room_type": "Loại phòng",
                "floor": "Tầng",
                "price": st.column_config.NumberColumn(
                    "Giá/đêm",
                    format="%,.0f VNĐ"
                ),
                "status": "Trạng thái"
            },
            use_container_width=True,
            hide_index=True
        )

    # --------------------------------------------------------
    # THÊM PHÒNG
    # --------------------------------------------------------

    with tab2:

        st.subheader("➕ Thêm phòng mới")

        with st.form("add_room_form"):

            col1, col2 = st.columns(2)

            with col1:
                room_number = st.text_input(
                    "Số phòng *"
                )

                room_type = st.selectbox(
                    "Loại phòng",
                    [
                        "Standard",
                        "Superior",
                        "Deluxe",
                        "Suite",
                        "VIP"
                    ]
                )

            with col2:
                floor = st.number_input(
                    "Tầng",
                    min_value=1,
                    max_value=100,
                    value=1
                )

                price = st.number_input(
                    "Giá phòng/đêm (VNĐ)",
                    min_value=0,
                    value=1500000,
                    step=100000
                )

            submit = st.form_submit_button(
                "➕ Thêm phòng",
                use_container_width=True
            )

            if submit:

                if not room_number.strip():
                    st.error("Vui lòng nhập số phòng.")

                else:

                    success, message = add_room(
                        room_number.strip(),
                        room_type,
                        floor,
                        price
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    # --------------------------------------------------------
    # CHỈNH SỬA
    # --------------------------------------------------------

    with tab3:

        st.subheader("✏️ Chỉnh sửa phòng")

        if rooms.empty:
            st.info("Chưa có phòng.")
        else:

            room_options = {
                f"{row['room_number']} - {row['room_type']}":
                row["id"]
                for _, row in rooms.iterrows()
            }

            selected_room = st.selectbox(
                "Chọn phòng",
                list(room_options.keys())
            )

            selected_id = room_options[selected_room]

            room = rooms[
                rooms["id"] == selected_id
            ].iloc[0]

            with st.form("edit_room_form"):

                col1, col2 = st.columns(2)

                with col1:

                    edit_number = st.text_input(
                        "Số phòng",
                        value=room["room_number"]
                    )

                    edit_type = st.selectbox(
                        "Loại phòng",
                        [
                            "Standard",
                            "Superior",
                            "Deluxe",
                            "Suite",
                            "VIP"
                        ],
                        index=[
                            "Standard",
                            "Superior",
                            "Deluxe",
                            "Suite",
                            "VIP"
                        ].index(room["room_type"])
                    )

                    edit_floor = st.number_input(
                        "Tầng",
                        min_value=1,
                        max_value=100,
                        value=int(room["floor"])
                    )

                with col2:

                    edit_price = st.number_input(
                        "Giá phòng/đêm",
                        min_value=0,
                        value=float(room["price"]),
                        step=100000.0
                    )

                    edit_status = st.selectbox(
                        "Trạng thái",
                        [
                            "Trống",
                            "Đã đặt",
                            "Đang ở",
                            "Đang dọn",
                            "Bảo trì"
                        ],
                        index=[
                            "Trống",
                            "Đã đặt",
                            "Đang ở",
                            "Đang dọn",
                            "Bảo trì"
                        ].index(room["status"])
                    )

                col_save, col_delete = st.columns(2)

                with col_save:
                    save = st.form_submit_button(
                        "💾 Lưu thay đổi",
                        use_container_width=True
                    )

                with col_delete:
                    delete = st.form_submit_button(
                        "🗑️ Xóa phòng",
                        use_container_width=True
                    )

                if save:

                    success, message = update_room(
                        selected_id,
                        edit_number,
                        edit_type,
                        edit_floor,
                        edit_price,
                        edit_status
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

                if delete:

                    success, message = delete_room(
                        selected_id
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


# ============================================================
# ĐẶT PHÒNG
# ============================================================

elif menu == "📅 Đặt phòng":

    st.title("📅 Đặt phòng")

    rooms = fetch_rooms()

    available_rooms = rooms[
        rooms["status"] == "Trống"
    ]

    if available_rooms.empty:

        st.warning(
            "Hiện tại không có phòng trống."
        )

    else:

        st.subheader("Thông tin khách")

        with st.form("booking_form"):

            col1, col2 = st.columns(2)

            with col1:

                full_name = st.text_input(
                    "Họ và tên khách *"
                )

                phone = st.text_input(
                    "Số điện thoại"
                )

                email = st.text_input(
                    "Email"
                )

                id_number = st.text_input(
                    "CCCD / Passport"
                )

            with col2:

                room_options = {
                    f"Phòng {row['room_number']} - "
                    f"{row['room_type']} - "
                    f"{format_money(row['price'])}/đêm":
                    row["id"]
                    for _, row in available_rooms.iterrows()
                }

                selected_room = st.selectbox(
                    "Chọn phòng *",
                    list(room_options.keys())
                )

                room_id = room_options[selected_room]

                check_in = st.date_input(
                    "Ngày nhận phòng",
                    value=date.today()
                )

                check_out = st.date_input(
                    "Ngày trả phòng",
                    value=date.today()
                )

                adults = st.number_input(
                    "Số người lớn",
                    min_value=1,
                    max_value=20,
                    value=1
                )

                children = st.number_input(
                    "Số trẻ em",
                    min_value=0,
                    max_value=20,
                    value=0
                )

            note = st.text_area(
                "Ghi chú"
            )

            submit_booking = st.form_submit_button(
                "📅 Xác nhận đặt phòng",
                use_container_width=True
            )

            if submit_booking:

                if not full_name.strip():
                    st.error(
                        "Vui lòng nhập họ tên khách."
                    )

                elif check_out <= check_in:
                    st.error(
                        "Ngày trả phòng phải sau ngày nhận phòng."
                    )

                else:

                    success, message = create_booking(
                        full_name,
                        phone,
                        email,
                        id_number,
                        room_id,
                        check_in,
                        check_out,
                        adults,
                        children,
                        note
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


# ============================================================
# KHÁCH LƯU TRÚ
# ============================================================

elif menu == "👤 Khách lưu trú":

    st.title("👤 Quản lý khách lưu trú")

    bookings = fetch_bookings()

    if bookings.empty:

        st.info("Chưa có khách lưu trú.")

    else:

        search_guest = st.text_input(
            "🔎 Tìm kiếm khách",
            placeholder="Nhập tên hoặc số điện thoại"
        )

        filtered = bookings.copy()

        if search_guest:

            mask = (
                filtered["full_name"]
                .astype(str)
                .str.contains(
                    search_guest,
                    case=False,
                    na=False
                )
                |
                filtered["phone"]
                .astype(str)
                .str.contains(
                    search_guest,
                    case=False,
                    na=False
                )
            )

            filtered = filtered[mask]

        st.dataframe(
            filtered,
            column_config={
                "id": "Booking ID",
                "full_name": "Khách hàng",
                "phone": "Điện thoại",
                "room_number": "Phòng",
                "room_type": "Loại phòng",
                "check_in": "Ngày nhận",
                "check_out": "Ngày trả",
                "adults": "NL",
                "children": "TE",
                "status": "Trạng thái",
                "total_amount": st.column_config.NumberColumn(
                    "Tổng tiền",
                    format="%,.0f VNĐ"
                ),
                "note": "Ghi chú"
            },
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("🔄 Cập nhật trạng thái")

        booking_options = {
            f"#{row['id']} - {row['full_name']} - "
            f"Phòng {row['room_number']}":
            row["id"]
            for _, row in bookings.iterrows()
        }

        selected_booking = st.selectbox(
            "Chọn booking",
            list(booking_options.keys())
        )

        booking_id = booking_options[selected_booking]

        col1, col2 = st.columns(2)

        with col1:

            new_status = st.selectbox(
                "Trạng thái mới",
                [
                    "Đã đặt",
                    "Đang ở",
                    "Đã trả phòng",
                    "Hủy"
                ]
            )

        with col2:

            if st.button(
                "💾 Cập nhật",
                use_container_width=True
            ):

                success, message = update_booking_status(
                    booking_id,
                    new_status
                )

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


# ============================================================
# THANH TOÁN
# ============================================================

elif menu == "💳 Thanh toán":

    st.title("💳 Thanh toán")

    bookings = fetch_bookings()

    if bookings.empty:

        st.info(
            "Chưa có booking để thanh toán."
        )

    else:

        booking_options = {
            f"#{row['id']} - {row['full_name']} - "
            f"Phòng {row['room_number']} - "
            f"{format_money(row['total_amount'])}":
            row["id"]
            for _, row in bookings.iterrows()
        }

        selected = st.selectbox(
            "Chọn booking",
            list(booking_options.keys())
        )

        booking_id = booking_options[selected]

        booking = bookings[
            bookings["id"] == booking_id
        ].iloc[0]

        st.divider()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Khách hàng",
            booking["full_name"]
        )

        col2.metric(
            "Phòng",
            booking["room_number"]
        )

        col3.metric(
            "Tổng tiền",
            format_money(
                booking["total_amount"]
            )
        )

        st.divider()

        with st.form("payment_form"):

            amount = st.number_input(
                "Số tiền thanh toán",
                min_value=0.0,
                value=float(
                    booking["total_amount"]
                ),
                step=100000.0
            )

            method = st.selectbox(
                "Phương thức thanh toán",
                [
                    "Tiền mặt",
                    "Chuyển khoản",
                    "Thẻ tín dụng",
                    "Ví điện tử"
                ]
            )

            note = st.text_area(
                "Ghi chú thanh toán"
            )

            submit_payment = st.form_submit_button(
                "💰 Xác nhận thanh toán",
                use_container_width=True
            )

            if submit_payment:

                if amount <= 0:
                    st.error(
                        "Số tiền phải lớn hơn 0."
                    )

                else:

                    make_payment(
                        booking_id,
                        amount,
                        method,
                        note
                    )

                    st.success(
                        "Thanh toán đã được ghi nhận."
                    )


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏨 Hotel Manager • Streamlit"
)
