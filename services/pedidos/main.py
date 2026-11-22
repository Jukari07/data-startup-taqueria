"""
API FastAPI para "Las Cazuelitas" - Plataforma de pedidos en línea para taquería.
Incluye autenticación JWT, gestión de menú, pedidos, ingesta CSV y health check.
"""

import csv
import io
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from services.pedidos.db import get_connection
from services.pedidos.cola import get_cola
from services.pedidos.storage import subir_raw, asegurar_buckets

# ---------------------------------------------------------------------------
# Configuración de la aplicación
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Las Cazuelitas API",
    description="API para gestión de pedidos de la taquería Las Cazuelitas. "
                "Permite registro/login de usuarios, consulta del menú, creación "
                "y seguimiento de pedidos, e ingesta masiva de pedidos via CSV.",
    version="2.0.0",
)


@app.on_event("startup")
def al_iniciar_api():
    """Asegura de forma idempotente que los buckets raw y clean existan al arrancar la API."""
    try:
        asegurar_buckets()
    except Exception as exc:
        print(f"[api] Advertencia al verificar/crear buckets de almacenamiento: {exc}")

# ---------------------------------------------------------------------------
# Seguridad: bcrypt + JWT
# ---------------------------------------------------------------------------
# Contexto de hashing de contraseñas usando bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de autenticación HTTP Bearer (extrae el token del header Authorization)
security = HTTPBearer()

# Clave secreta para firmar los tokens JWT (debe estar en variable de entorno)
JWT_SECRET = os.getenv("API_SECRET_KEY", "CAMBIA_ESTO_EN_PRODUCCION")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Token de API para el endpoint de ingesta masiva
API_TOKEN = os.getenv("API_TOKEN", "CAMBIA_ESTO_EN_PRODUCCION")


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class ItemPedido(BaseModel):
    """Representa un ítem dentro de un pedido."""
    producto_id: int
    cantidad: int
    salsa: str  # 'verde', 'roja' o 'sin_salsa'


class CrearPedido(BaseModel):
    """Cuerpo de la solicitud para crear un nuevo pedido."""
    tipo_entrega: str          # 'llevar', 'aqui' o 'domicilio'
    notas: Optional[str] = None
    items: List[ItemPedido]


class RespuestaPedido(BaseModel):
    """Respuesta devuelta al crear un pedido exitosamente."""
    pedido_id: str
    estado: str
    total: float
    mensaje: str


# ---------------------------------------------------------------------------
# Utilidades de autenticación
# ---------------------------------------------------------------------------

def hashear_password(password: str) -> str:
    """Genera el hash bcrypt de una contraseña en texto plano (máx 72 bytes según especificación bcrypt)."""
    pw_bytes = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(pw_bytes)


def verificar_password(password: str, password_hash: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    pw_bytes = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.verify(pw_bytes, password_hash)


def crear_token_jwt(data: dict) -> str:
    """
    Crea y firma un token JWT con los datos del usuario.
    El token expira según JWT_EXPIRE_MINUTES.
    """
    payload = data.copy()
    expiracion = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload.update({"exp": expiracion})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependencia que valida el token JWT del header Authorization: Bearer <token>.
    Retorna el payload del token si es válido, o lanza 401 si no lo es.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: falta el identificador de usuario.",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )


def requerir_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependencia que verifica que el usuario tenga rol 'admin'."""
    if current_user.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de administrador.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Endpoints de Autenticación
# ---------------------------------------------------------------------------

@app.post("/auth/registro", status_code=status.HTTP_201_CREATED, tags=["Autenticación"])
def registro(nombre: str, email: str, password: str):
    """
    Registra un nuevo usuario en el sistema.
    - Hashea la contraseña con bcrypt antes de guardarla.
    - Retorna un token JWT listo para usar.
    """
    password_hash = hashear_password(password)
    nuevo_id = str(uuid.uuid4())

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verificar si el email ya está registrado
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un usuario con ese correo electrónico.",
                )
            # Insertar el nuevo usuario con rol 'cliente' por defecto
            cur.execute(
                """
                INSERT INTO usuarios (id, nombre, email, password_hash, rol)
                VALUES (%s, %s, %s, %s, 'cliente')
                """,
                (nuevo_id, nombre, email, password_hash),
            )
        conn.commit()

    token = crear_token_jwt({"sub": nuevo_id, "email": email, "rol": "cliente"})
    return {"access_token": token, "token_type": "bearer", "usuario_id": nuevo_id}


@app.post("/auth/login", tags=["Autenticación"])
def login(email: str, password: str):
    """
    Autentica a un usuario existente.
    - Valida las credenciales contra la base de datos.
    - Retorna un token JWT si las credenciales son correctas.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, rol FROM usuarios WHERE email = %s",
                (email,),
            )
            fila = cur.fetchone()

    if not fila or not verificar_password(password, fila[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )

    token = crear_token_jwt({"sub": str(fila[0]), "email": email, "rol": fila[2]})
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Endpoints de Menú
# ---------------------------------------------------------------------------

@app.get("/menu", tags=["Menú"])
def obtener_menu():
    """
    Retorna la lista de productos activos del menú.
    No requiere autenticación.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nombre, categoria, precio_unitario
                FROM productos
                WHERE activo = TRUE
                ORDER BY categoria, nombre
                """
            )
            columnas = [desc[0] for desc in cur.description]
            productos = [dict(zip(columnas, fila)) for fila in cur.fetchall()]

    return {"productos": productos, "total": len(productos)}


# ---------------------------------------------------------------------------
# Endpoints de Pedidos
# ---------------------------------------------------------------------------

@app.post("/pedidos", response_model=RespuestaPedido, tags=["Pedidos"])
def crear_pedido(
    pedido: CrearPedido,
    current_user: dict = Depends(get_current_user),
):
    """
    Crea un nuevo pedido para el usuario autenticado.
    - Valida que todos los productos existan y estén activos.
    - Calcula el total automáticamente.
    - Guarda el pedido y su detalle en PostgreSQL.
    - Serializa el pedido a CSV y lo sube a MinIO (zona raw/).
    - Publica un mensaje en la cola de procesamiento.
    """
    # Validar tipo de entrega
    tipos_validos = {"llevar", "aqui", "domicilio"}
    if pedido.tipo_entrega not in tipos_validos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tipo_entrega debe ser uno de: {tipos_validos}",
        )

    # Validar que venga al menos un ítem
    if not pedido.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El pedido debe contener al menos un ítem.",
        )

    salsas_validas = {"verde", "roja", "sin_salsa"}
    pedido_id = str(uuid.uuid4())
    total = 0.0
    detalles_para_insertar = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in pedido.items:
                # Validar salsa
                if item.salsa not in salsas_validas:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Salsa '{item.salsa}' inválida. Opciones: {salsas_validas}",
                    )
                # Validar que el producto exista y esté activo
                cur.execute(
                    "SELECT precio_unitario FROM productos WHERE id = %s AND activo = TRUE",
                    (item.producto_id,),
                )
                producto = cur.fetchone()
                if not producto:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Producto {item.producto_id} no encontrado o no disponible.",
                    )
                precio = float(producto[0])
                subtotal = precio * item.cantidad
                total += subtotal
                detalles_para_insertar.append(
                    (pedido_id, item.producto_id, item.salsa, item.cantidad, precio, subtotal)
                )

            # Insertar el pedido principal
            cur.execute(
                """
                INSERT INTO pedidos (pedido_id, cliente_id, tipo_entrega, estado, notas, total)
                VALUES (%s, %s, %s, 'pendiente', %s, %s)
                """,
                (pedido_id, current_user["sub"], pedido.tipo_entrega, pedido.notas, total),
            )
            # Insertar el detalle del pedido
            for detalle in detalles_para_insertar:
                cur.execute(
                    """
                    INSERT INTO detalle_pedido
                        (pedido_id, producto_id, salsa, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    detalle,
                )
        conn.commit()

    # Serializar el pedido a CSV y subir a MinIO zona raw/
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["pedido_id", "producto_id", "cantidad", "salsa", "precio_unitario", "subtotal"])
    for d in detalles_para_insertar:
        writer.writerow([d[0], d[1], d[3], d[2], d[4], d[5]])
    nombre_csv = f"pedidos_{pedido_id}.csv"
    path_raw = subir_raw(buffer.getvalue().encode("utf-8"), nombre_csv)

    # Publicar en la cola para que el worker procese el pedido
    cola = get_cola()
    try:
        cola.publicar({
            "pedido_id": pedido_id,
            "path_raw": path_raw,
            "cliente_id": current_user["sub"],
            "timestamp": datetime.utcnow().isoformat(),
        })
    finally:
        cola.cerrar()

    return RespuestaPedido(
        pedido_id=pedido_id,
        estado="pendiente",
        total=total,
        mensaje="Pedido creado correctamente y enviado a procesamiento.",
    )


@app.get("/pedidos/{pedido_id}", tags=["Pedidos"])
def obtener_pedido(pedido_id: str, current_user: dict = Depends(get_current_user)):
    """
    Retorna el detalle de un pedido específico.
    - Solo el propietario del pedido o un admin pueden verlo.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.pedido_id, p.cliente_id, p.fecha_hora, p.tipo_entrega,
                       p.estado, p.notas, p.total
                FROM pedidos p
                WHERE p.pedido_id = %s
                """,
                (pedido_id,),
            )
            fila = cur.fetchone()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado.",
        )

    # Verificar que el usuario sea el dueño o admin
    es_admin = current_user.get("rol") == "admin"
    es_dueno = str(fila[1]) == current_user["sub"]
    if not es_admin and not es_dueno:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este pedido.",
        )

    return {
        "pedido_id": str(fila[0]),
        "cliente_id": str(fila[1]),
        "fecha_hora": fila[2].isoformat() if fila[2] else None,
        "tipo_entrega": fila[3],
        "estado": fila[4],
        "notas": fila[5],
        "total": float(fila[6]) if fila[6] else 0.0,
    }


@app.get("/pedidos", tags=["Pedidos"])
def listar_pedidos(
    pagina: int = Query(1, ge=1, description="Número de página"),
    por_pagina: int = Query(20, ge=1, le=100, description="Resultados por página"),
    current_user: dict = Depends(requerir_admin),
):
    """
    Lista todos los pedidos con paginación. Solo accesible para administradores.
    """
    offset = (pagina - 1) * por_pagina
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM pedidos")
            total_pedidos = cur.fetchone()[0]

            cur.execute(
                """
                SELECT pedido_id, cliente_id, fecha_hora, tipo_entrega, estado, total
                FROM pedidos
                ORDER BY fecha_hora DESC
                LIMIT %s OFFSET %s
                """,
                (por_pagina, offset),
            )
            columnas = [desc[0] for desc in cur.description]
            pedidos = [dict(zip(columnas, fila)) for fila in cur.fetchall()]

    # Convertir tipos no serializables
    for p in pedidos:
        if p.get("fecha_hora"):
            p["fecha_hora"] = p["fecha_hora"].isoformat()
        p["pedido_id"] = str(p["pedido_id"])
        p["cliente_id"] = str(p["cliente_id"])

    return {
        "pedidos": pedidos,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total": total_pedidos,
        "paginas_totales": -(-total_pedidos // por_pagina),  # Ceil division
    }


@app.post("/ingesta/csv", tags=["Ingesta"])
async def ingestar_csv(
    archivo: UploadFile = File(..., description="Archivo CSV con pedidos"),
    x_api_token: str = Header(..., alias="X-API-Token"),
):
    """
    Acepta un archivo CSV multipart y lo procesa para ingesta masiva.
    - Requiere token de API en el header X-API-Token.
    - Valida las columnas requeridas.
    - Sube el CSV a MinIO zona raw/.
    - Publica un mensaje en la cola para procesamiento.
    """
    # Validar token de API
    if x_api_token != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de API inválido.",
        )

    # Leer y validar el contenido del CSV
    contenido = await archivo.read()
    try:
        texto = contenido.decode("utf-8")
        reader = csv.DictReader(io.StringIO(texto))
        columnas_requeridas = {"pedido_id", "producto_id", "cantidad", "salsa"}
        if not columnas_requeridas.issubset(set(reader.fieldnames or [])):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El CSV debe contener las columnas: {columnas_requeridas}. "
                       f"Columnas encontradas: {reader.fieldnames}",
            )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo debe estar codificado en UTF-8.",
        )

    # Subir a MinIO zona raw/
    nombre_csv = f"ingesta_{uuid.uuid4()}.csv"
    path_raw = subir_raw(contenido, nombre_csv)

    # Publicar en la cola
    cola = get_cola()
    try:
        cola.publicar({
            "tipo": "ingesta_masiva",
            "path_raw": path_raw,
            "timestamp": datetime.utcnow().isoformat(),
        })
    finally:
        cola.cerrar()

    return {
        "mensaje": "CSV recibido y enviado a procesamiento.",
        "path": path_raw,
        "filas_detectadas": sum(1 for _ in csv.DictReader(io.StringIO(texto))),
    }


# ---------------------------------------------------------------------------
# Endpoint de Health Check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
def health():
    """
    Verifica que la API esté en funcionamiento.
    No requiere autenticación. Usado por Docker y load balancers.
    """
    return {"status": "ok", "version": "2.0.0", "servicio": "Las Cazuelitas API"}
