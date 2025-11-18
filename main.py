from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware  # <-- ДОБАВЬ ЭТО
from datetime import datetime
import database
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

app = FastAPI(title="Tennis Court Booking")

# ДОБАВЬ CORS ДЛЯ TELEGRAM
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_time_slots():
    slots = []
    for hour in range(6, 24):
        start = f"{hour:02d}:00"
        end = f"{(hour + 1):02d}:00"
        slots.append(f"{start}-{end}")
    return slots


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Запись на теннисный корт</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .court { margin: 20px 0; padding: 10px; border: 1px solid #ccc; }
            .slot { padding: 10px; margin: 5px; border: 1px solid #ddd; display: inline-block; }
            .available { background: #90EE90; cursor: pointer; }
            .booked { background: #FFB6C1; }
            .tabs { display: flex; margin-bottom: 20px; }
            .tab { padding: 10px; border: 1px solid #ccc; cursor: pointer; }
            .active { background: #007bff; color: white; }
        </style>
    </head>
    <body>
        <h1>🎾 Запись на теннисный корт</h1>

        <div class="tabs">
            <div class="tab active" onclick="showTab('booking')">Записаться</div>
            <div class="tab" onclick="showTab('my-bookings')">Мои записи</div>
        </div>

        <div id="booking-tab">
            <h3>Выберите дату:</h3>
            <input type="date" id="date-picker" onchange="loadSlots()">

            <h3>Выберите корт:</h3>
            <button onclick="selectCourt('rubber')">Резиновый</button>
            <button onclick="selectCourt('hard')">Хард</button>

            <div id="slots-container"></div>
        </div>

        <div id="my-bookings-tab" style="display:none;">
            <h3>Мои записи:</h3>
            <div id="bookings-list"></div>
        </div>

        <script>
            let currentCourt = 'rubber';
            let currentUser = { id: 123456, first_name: 'Тестовый пользователь' };

            function showTab(tabName) {
                document.getElementById('booking-tab').style.display = 'none';
                document.getElementById('my-bookings-tab').style.display = 'none';
                document.getElementById(tabName + '-tab').style.display = 'block';

                if (tabName === 'my-bookings') {
                    loadMyBookings();
                }
            }

            function selectCourt(court) {
                currentCourt = court;
                loadSlots();
            }

            async function loadSlots() {
                const date = document.getElementById('date-picker').value;
                if (!date) return;

                const response = await fetch('/api/slots?date=' + date);
                const slots = await response.json();

                const container = document.getElementById('slots-container');
                container.innerHTML = '<h3>Доступные слоты:</h3>';

                slots.forEach(slot => {
                    if (slot.court_type === currentCourt) {
                        const slotElement = document.createElement('div');
                        slotElement.className = 'slot ' + (slot.is_available ? 'available' : 'booked');
                        slotElement.innerHTML = slot.time_slot + (slot.is_available ? ' - Свободно' : ' - Занято: ' + slot.booked_by);

                        if (slot.is_available) {
                            slotElement.onclick = () => bookSlot(slot);
                        }

                        container.appendChild(slotElement);
                    }
                });
            }

            async function bookSlot(slot) {
                if (!confirm('Записаться на ' + slot.time_slot + '?')) return;

                const response = await fetch('/api/book', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: currentUser.id,
                        first_name: currentUser.first_name,
                        court_type: slot.court_type,
                        date: slot.date,
                        time_slot: slot.time_slot
                    })
                });

                const result = await response.json();
                alert(result.message);
                loadSlots();
            }

            async function loadMyBookings() {
                const response = await fetch('/api/my-bookings?user_id=' + currentUser.id);
                const bookings = await response.json();

                const container = document.getElementById('bookings-list');
                container.innerHTML = '';

                bookings.forEach(booking => {
                    const bookingElement = document.createElement('div');
                    bookingElement.className = 'court';
                    bookingElement.innerHTML = `
                        ${booking.date} ${booking.time_slot} (${booking.court_type === 'rubber' ? 'Резиновый' : 'Хард'})
                        <button onclick="cancelBooking(${booking.id})">Отменить</button>
                    `;
                    container.appendChild(bookingElement);
                });
            }

            async function cancelBooking(bookingId) {
                if (!confirm('Отменить запись?')) return;

                const response = await fetch('/api/booking/' + bookingId + '?user_id=' + currentUser.id, {
                    method: 'DELETE'
                });

                const result = await response.json();
                alert(result.message);
                loadMyBookings();
            }

            // Устанавливаем сегодняшнюю дату по умолчанию
            document.getElementById('date-picker').value = new Date().toISOString().split('T')[0];
            loadSlots();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Остальной код API оставляем как был
@app.get("/api/slots")
async def get_slots(date: str = Query(...)):
    conn = database.db.get_connection()
    cursor = conn.cursor()

    time_slots = generate_time_slots()
    court_types = ['rubber', 'hard']
    slots = []

    for court_type in court_types:
        for time_slot in time_slots:
            cursor.execute('''
                SELECT b.id, u.first_name 
                FROM bookings b 
                LEFT JOIN users u ON b.user_id = u.user_id 
                WHERE b.court_type = ? AND b.date = ? AND b.time_slot = ?
            ''', (court_type, date, time_slot))

            booking = cursor.fetchone()

            if booking:
                slots.append({
                    "court_type": court_type,
                    "date": date,
                    "time_slot": time_slot,
                    "is_available": False,
                    "booked_by": booking['first_name'],
                    "booking_id": booking['id']
                })
            else:
                slots.append({
                    "court_type": court_type,
                    "date": date,
                    "time_slot": time_slot,
                    "is_available": True,
                    "booked_by": None,
                    "booking_id": None
                })

    conn.close()
    return slots


@app.post("/api/book")
async def create_booking(booking_data: dict):
    conn = database.db.get_connection()
    cursor = conn.cursor()

    # Проверяем запись на этот день
    cursor.execute(
        'SELECT id FROM bookings WHERE user_id = ? AND date = ?',
        (booking_data['user_id'], booking_data['date'])
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Вы уже записаны на этот день")

    # Проверяем свободен ли слот
    cursor.execute(
        'SELECT id FROM bookings WHERE court_type = ? AND date = ? AND time_slot = ?',
        (booking_data['court_type'], booking_data['date'], booking_data['time_slot'])
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Это время уже занято")

    # Сохраняем пользователя
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)',
        (booking_data['user_id'], booking_data['first_name'])
    )

    # Создаем запись
    cursor.execute(
        'INSERT INTO bookings (user_id, court_type, date, time_slot) VALUES (?, ?, ?, ?)',
        (booking_data['user_id'], booking_data['court_type'], booking_data['date'], booking_data['time_slot'])
    )

    conn.commit()
    conn.close()

    return {"success": True, "message": "Запись успешно создана!"}


@app.get("/api/my-bookings")
async def get_my_bookings(user_id: int = Query(...)):
    conn = database.db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, court_type, date, time_slot 
        FROM bookings 
        WHERE user_id = ? AND date >= date('now') 
        ORDER BY date, time_slot
    ''', (user_id,))

    bookings = cursor.fetchall()
    conn.close()

    return [dict(booking) for booking in bookings]


@app.delete("/api/booking/{booking_id}")
async def cancel_booking(booking_id: int, user_id: int = Query(...)):
    conn = database.db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM bookings WHERE id = ? AND user_id = ?',
        (booking_id, user_id)
    )

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Запись не найдена")

    conn.commit()
    conn.close()

    return {"success": True, "message": "Запись отменена"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)