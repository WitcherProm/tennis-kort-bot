from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import database
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

app = FastAPI(title="Tennis Court Booking")

# Добавляем CORS для Telegram
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
            .slot { 
                padding: 10px; 
                margin: 5px; 
                border: 1px solid #ddd; 
                display: inline-block;
                width: 150px;
                text-align: center;
            }
            .available { background: #90EE90; cursor: pointer; }
            .booked { background: #FFB6C1; }
            .tabs { display: flex; margin-bottom: 20px; }
            .tab { padding: 10px; border: 1px solid #ccc; cursor: pointer; }
            .active { background: #007bff; color: white; }
            .court-buttons { margin: 15px 0; }
            .court-button { 
                padding: 10px 20px; 
                margin: 5px; 
                border: 2px solid #007bff;
                background: white;
                cursor: pointer;
                border-radius: 5px;
            }
            .court-button.active { 
                background: #007bff; 
                color: white; 
            }
            .slots-grid { 
                display: grid; 
                grid-template-columns: repeat(2, 1fr); 
                gap: 10px; 
                max-width: 400px;
            }
            .user-info {
                background: #f0f8ff;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 15px;
                border-left: 4px solid #007bff;
            }
            .loading { 
                display: none;
                text-align: center; 
                padding: 20px; 
                color: #666; 
            }
            .error { 
                display: none;
                background: #ffebee; 
                color: #c62828; 
                padding: 10px; 
                border-radius: 5px; 
                margin: 10px 0; 
            }
        </style>
    </head>
    <body>
        <div id="loading" class="loading">
            <h2>🎾 Загружаем расписание...</h2>
            <p>Пожалуйста, подождите</p>
        </div>

        <div id="content" style="display:none;">
            <h1>🎾 Запись на теннисный корт</h1>
            
            <div id="user-info" class="user-info" style="display:none;">
                Добро пожаловать, <span id="user-name">Гость</span>!
                <button onclick="resetUser()" style="margin-left: 10px; font-size: 12px;">Сбросить</button>
            </div>

            <div id="error-message" class="error"></div>

            <div class="tabs">
                <div class="tab active" onclick="showTab('booking')">Записаться</div>
                <div class="tab" onclick="showTab('my-bookings')">Мои записи</div>
            </div>

            <div id="booking-tab">
                <h3>Выберите дату:</h3>
                <input type="date" id="date-picker" onchange="loadSlots()">

                <h3>Выберите корт:</h3>
                <div class="court-buttons">
                    <button id="court-rubber" class="court-button active" onclick="selectCourt('rubber')">Резиновый</button>
                    <button id="court-hard" class="court-button" onclick="selectCourt('hard')">Хард</button>
                </div>

                <div id="slots-container"></div>
            </div>

            <div id="my-bookings-tab" style="display:none;">
                <h3>Мои записи:</h3>
                <div id="bookings-list"></div>
            </div>
        </div>

        <script>
            let currentCourt = 'rubber';
            let currentUser = null;
            let isInitialized = false;

            function showLoading() {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('content').style.display = 'none';
            }

            function hideLoading() {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
            }

            function showError(message) {
                const errorDiv = document.getElementById('error-message');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
                setTimeout(() => errorDiv.style.display = 'none', 5000);
            }

            async function initTelegramUser() {
                console.log('=== INIT TELEGRAM USER ===');
                
                try {
                    // Быстрая инициализация - сначала проверяем localStorage
                    const savedUser = localStorage.getItem('telegramUser');
                    if (savedUser) {
                        currentUser = JSON.parse(savedUser);
                        console.log('📁 User from localStorage:', currentUser);
                        showUserInfo(currentUser);
                        return true;
                    }
                    
                    // Проверяем Telegram WebApp (быстрая проверка)
                    if (window.Telegram && window.Telegram.WebApp) {
                        console.log('✅ Telegram WebApp detected');
                        const tg = window.Telegram.WebApp;
                        
                        // Быстрая инициализация
                        tg.ready();
                        
                        // Проверяем пользователя без долгих операций
                        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
                            const user = tg.initDataUnsafe.user;
                            console.log('👤 User from Telegram:', user);
                            
                            currentUser = {
                                id: user.id,
                                first_name: user.first_name || 'Telegram User',
                                username: user.username || '',
                                last_name: user.last_name || '',
                                language_code: user.language_code || 'ru'
                            };
                            
                            localStorage.setItem('telegramUser', JSON.stringify(currentUser));
                            showUserInfo(currentUser);
                            return true;
                        }
                    }
                    
                    // Если не нашли пользователя - создаем гостя
                    console.log('👤 Creating guest user');
                    currentUser = { 
                        id: Math.floor(Math.random() * 1000000), 
                        first_name: 'Гость'
                    };
                    localStorage.setItem('telegramUser', JSON.stringify(currentUser));
                    showUserInfo(currentUser);
                    return true;
                    
                } catch (error) {
                    console.error('Error initializing user:', error);
                    // В случае ошибки всё равно создаем гостя
                    currentUser = { 
                        id: Math.floor(Math.random() * 1000000), 
                        first_name: 'Гость'
                    };
                    showUserInfo(currentUser);
                    return true;
                }
            }

            function showUserInfo(user) {
                try {
                    const userName = user.first_name + (user.last_name ? ' ' + user.last_name : '');
                    document.getElementById('user-name').textContent = userName;
                    document.getElementById('user-info').style.display = 'block';
                    console.log(`👤 User: ${userName}`);
                } catch (error) {
                    console.error('Error showing user info:', error);
                }
            }

            function resetUser() {
                localStorage.removeItem('telegramUser');
                currentUser = null;
                document.getElementById('user-info').style.display = 'none';
                setTimeout(() => location.reload(), 100);
            }

            async function initializeApp() {
                showLoading();
                console.log('🚀 Initializing app...');
                
                try {
                    // Инициализируем пользователя
                    await initTelegramUser();
                    
                    // Устанавливаем сегодняшнюю дату
                    document.getElementById('date-picker').value = new Date().toISOString().split('T')[0];
                    
                    // Загружаем слоты
                    await loadSlots();
                    
                    // Показываем интерфейс
                    hideLoading();
                    isInitialized = true;
                    console.log('✅ App initialized successfully');
                    
                } catch (error) {
                    console.error('❌ App initialization failed:', error);
                    hideLoading();
                    showError('Ошибка загрузки. Пожалуйста, обновите страницу.');
                }
            }

            function showTab(tabName) {
                if (!isInitialized) return;
                
                document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                event.target.classList.add('active');
                
                document.getElementById('booking-tab').style.display = 'none';
                document.getElementById('my-bookings-tab').style.display = 'none';
                document.getElementById(tabName + '-tab').style.display = 'block';

                if (tabName === 'my-bookings') {
                    loadMyBookings();
                }
            }

            function selectCourt(court) {
                if (!isInitialized) return;
                
                currentCourt = court;
                document.getElementById('court-rubber').classList.remove('active');
                document.getElementById('court-hard').classList.remove('active');
                document.getElementById('court-' + court).classList.add('active');
                loadSlots();
            }

            async function loadSlots() {
                if (!isInitialized) return;
                
                const date = document.getElementById('date-picker').value;
                if (!date) return;

                try {
                    const response = await fetch('/api/slots?date=' + date);
                    if (!response.ok) throw new Error('Network error');
                    
                    const slots = await response.json();

                    const container = document.getElementById('slots-container');
                    container.innerHTML = '<h3>Доступные слоты:</h3>';
                    
                    const grid = document.createElement('div');
                    grid.className = 'slots-grid';

                    const courtSlots = slots
                        .filter(slot => slot.court_type === currentCourt)
                        .sort((a, b) => a.time_slot.localeCompare(b.time_slot));

                    courtSlots.forEach(slot => {
                        const slotElement = document.createElement('div');
                        slotElement.className = 'slot ' + (slot.is_available ? 'available' : 'booked');
                        slotElement.innerHTML = slot.time_slot.replace('-', '<br>') + 
                            (slot.is_available ? '<br><small>Свободно</small>' : '<br><small>Занято: ' + slot.booked_by + '</small>');

                        if (slot.is_available) {
                            slotElement.onclick = () => bookSlot(slot);
                        }

                        grid.appendChild(slotElement);
                    });

                    container.appendChild(grid);
                } catch (error) {
                    console.error('Error loading slots:', error);
                    showError('Ошибка загрузки расписания');
                }
            }

            async function bookSlot(slot) {
                if (!currentUser || !isInitialized) {
                    alert('Приложение не готово');
                    return;
                }

                if (!confirm('Записаться на ' + slot.time_slot + '?')) return;

                try {
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
                    if (result.success) {
                        alert('Успешно записаны!');
                        loadSlots();
                    } else {
                        alert('Ошибка: ' + result.detail);
                    }
                } catch (error) {
                    console.error('Error booking slot:', error);
                    alert('Ошибка при записи');
                }
            }

            async function loadMyBookings() {
                if (!currentUser || !isInitialized) {
                    alert('Приложение не готово');
                    return;
                }

                try {
                    const response = await fetch('/api/my-bookings?user_id=' + currentUser.id);
                    const bookings = await response.json();

                    const container = document.getElementById('bookings-list');
                    container.innerHTML = '';

                    if (bookings.length === 0) {
                        container.innerHTML = '<p>У вас нет активных записей</p>';
                        return;
                    }

                    bookings.forEach(booking => {
                        const bookingElement = document.createElement('div');
                        bookingElement.className = 'court';
                        bookingElement.innerHTML = `
                            <strong>${booking.date}</strong> ${booking.time_slot.replace('-', ' - ')} 
                            (${booking.court_type === 'rubber' ? 'Резиновый' : 'Хард'})
                            <button onclick="cancelBooking(${booking.id})" style="margin-left: 10px;">Отменить</button>
                        `;
                        container.appendChild(bookingElement);
                    });
                } catch (error) {
                    console.error('Error loading bookings:', error);
                    showError('Ошибка загрузки записей');
                }
            }

            async function cancelBooking(bookingId) {
                if (!confirm('Отменить запись?')) return;

                try {
                    const response = await fetch('/api/booking/' + bookingId + '?user_id=' + currentUser.id, {
                        method: 'DELETE'
                    });

                    const result = await response.json();
                    alert(result.message);
                    loadMyBookings();
                } catch (error) {
                    console.error('Error canceling booking:', error);
                    alert('Ошибка при отмене записи');
                }
            }

            // Инициализация при загрузке
            document.addEventListener('DOMContentLoaded', function() {
                console.log('📄 DOM loaded');
                setTimeout(() => {
                    initializeApp();
                }, 100);
            });

            // Резервная инициализация на случай если что-то пошло не так
            setTimeout(() => {
                if (!isInitialized) {
                    console.log('🕒 Backup initialization');
                    initializeApp();
                }
            }, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Остальной код API без изменений
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
