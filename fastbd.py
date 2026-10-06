import sqlite3
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="Fast db",
    description="Демонстрационный модуль бэкенда для интеграции с фронтендом на Next.js",
    version="1.0.0"
)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("FASTAPIDB.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            skin_name TEXT NOT NULL,
            price_usdt REAL NOT NULL,
            status TEXT DEFAULT 'В продаже'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- PYDANTIC СХЕМЫ ДЛЯ ВАЛИДАЦИИ ДАННЫХ (Для Next.js / TypeScript) ---
class OfferCreateSchema(BaseModel):
    seller_id: int = Field(..., description="ID продавца из Системы")
    skin_name: str = Field(..., min_length=2, description="Полное название предмета")
    price_usdt: float = Field(..., gt=0, description="Цена лота, больше 0")

    class Config:
        json_schema_extra = {
            "example": {
                "seller_id": 123456789,
                "skin_name": "AK-47 | Redline (Field-Tested)",
                "price_usdt": 15.50
            }
        }


# --- API ЭНДПОИНТЫ ---

@app.get("/api/v1/offers", tags=["Offers"])
async def get_active_offers():
    """Получение всех активных лотов на маркетплейсе."""
    conn = sqlite3.connect("FASTAPIDB.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, seller_id, skin_name, price_usdt, status FROM offers WHERE status = 'В продаже'")
    rows = cursor.fetchall()
    conn.close()
    
    # JSON
    return [
        {
            "id": r[0], 
            "seller_id": r[1], 
            "skin_name": r[2], 
            "price_usdt": r[3], 
            "status": r[4]
        } for r in rows
    ]


@app.post("/api/v1/offers", tags=["Offers"], status_code=status.HTTP_201_CREATED)
async def create_p2p_offer(offer_data: OfferCreateSchema):
    """
    Создание нового лота с защитой от дубликатов (Анти-дюп логика).
    Принимает структурированный JSON Body от фронтенда.
    """
    conn = sqlite3.connect("FASTAPIDB.db")
    cursor = conn.cursor()
    
    # проверка на существование повторяющегося активного лота
    cursor.execute(
        "SELECT id FROM offers WHERE seller_id = ? AND skin_name = ? AND status = 'В продаже'",
        (offer_data.seller_id, offer_data.skin_name)
    )
    existing_offer = cursor.fetchone()
    
    if existing_offer:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Выставление заблокировано. Лот '{offer_data.skin_name}' уже активно продается вами."
        )
        
    try:
        cursor.execute(
            "INSERT INTO offers (seller_id, skin_name, price_usdt) VALUES (?, ?, ?)",
            (offer_data.seller_id, offer_data.skin_name, offer_data.price_usdt)
        )
        conn.commit()
        return {"status": "success", "message": "Лот успешно сохранен и выведен на витрину."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при записи в базу данных: {str(e)}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastbd:app", host="127.0.0.1", port=8000, reload=True)