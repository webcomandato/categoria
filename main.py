from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import xml.etree.ElementTree as ET
from typing import List, Optional
import logging
import asyncio
import xmltodict

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Definir el modelo de datos para los productos
class Product(BaseModel):
    title: str
    summary: Optional[str] = ""
    link: str
    category: Optional[str] = ""

# Crear la aplicación FastAPI
app = FastAPI(
    title="API de Productos Comandato por Categorías",
    description="API para obtener productos de Comandato desde su feed XML organizados por categorías",
    version="1.0.0"
)

# Configurar CORS para permitir solicitudes desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL del feed XML de Comandato
XML_FEED_URL = "https://www.comandato.com/XMLData/atomfeed.xml"

# Función para clasificar productos según su título
def categorize_product(title):
    title_lower = title.lower()
    
    if any(keyword in title_lower for keyword in ["televisor", "led", "smart tv", "uhd", "4k", "nanocell"]):
        return "Televisores"
    elif any(keyword in title_lower for keyword in ["parlante", "torre de sonido", "barra de sonido", "minicomponente", "sound bar"]):
        return "Parlantes"
    elif any(keyword in title_lower for keyword in ["celular", "iphone", "smartphone", "honor", "infinix", "tecno"]):
        return "Celulares"
    elif any(keyword in title_lower for keyword in ["laptop", "portátil", "notebook", "core i", "ryzen"]):
        return "Laptops"
    elif any(keyword in title_lower for keyword in ["impresora", "multifunción", "epson", "canon", "brother"]):
        return "Impresoras"
    elif any(keyword in title_lower for keyword in ["cocina a gas", "cocina", "hornilla", "quemador", "indurama", "mabe"]) and "microonda" not in title_lower:
        return "Cocina a gas"
    elif any(keyword in title_lower for keyword in ["refrigeradora", "side by side", "top freezer"]):
        return "Refrigeradoras"
    elif any(keyword in title_lower for keyword in ["frigobar"]):
        return "Frigobares"
    elif any(keyword in title_lower for keyword in ["congelador", "horizontal"]):
        return "Congeladores"
    elif any(keyword in title_lower for keyword in ["vitrina"]):
        return "Vitrinas"
    elif any(keyword in title_lower for keyword in ["lavadora", "automática", "semiautomática"]):
        return "Lavadoras"
    elif any(keyword in title_lower for keyword in ["secadora"]):
        return "Secadoras"
    elif any(keyword in title_lower for keyword in ["torre de lavado"]):
        return "Torres de lavado"
    elif any(keyword in title_lower for keyword in ["aire acondicionado", "split", "btu"]):
        return "Aire Acondicionado Split"
    elif any(keyword in title_lower for keyword in ["cafetera", "máquina de café"]):
        return "Cafeteras"
    elif any(keyword in title_lower for keyword in ["canguilera"]):
        return "Canguileras"
    elif any(keyword in title_lower for keyword in ["microonda", "microondas"]):
        return "Horno Microondas"
    elif any(keyword in title_lower for keyword in ["freidora", "airfryer"]):
        return "Freidoras"
    elif any(keyword in title_lower for keyword in ["licuadora"]):
        return "Licuadoras"
    elif any(keyword in title_lower for keyword in ["olla", "arrocera"]):
        return "Ollas"
    elif any(keyword in title_lower for keyword in ["exprimidor", "extractor de jugo"]):
        return "Exprimidores"
    elif any(keyword in title_lower for keyword in ["sanduchera", "grill"]):
        return "Sanducheras"
    elif any(keyword in title_lower for keyword in ["plancha"]):
        return "Planchas"
    elif any(keyword in title_lower for keyword in ["hervidor", "eléctrico"]):
        return "Hervidores"
    else:
        return "Otros"

# Función para obtener y parsear los productos del feed XML
async def fetch_products():
    max_retries = 3
    retry_count = 0
    timeout = httpx.Timeout(30.0, read=60.0)
    
    while retry_count < max_retries:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.debug(f"Intento {retry_count+1} de obtener datos de {XML_FEED_URL}")
                response = await client.get(XML_FEED_URL)
                response.raise_for_status()
                
                # Convertir XML a diccionario
                data = xmltodict.parse(response.text)
                
                products = []
                entries = data.get('feed', {}).get('entry', [])
                
                # Si solo hay una entrada, convertirla a lista
                if not isinstance(entries, list):
                    entries = [entries]
                    
                for entry in entries:
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    link = entry.get('link', '')
                    
                    # Si link es un diccionario (común en algunos feeds)
                    if isinstance(link, dict):
                        link = link.get('@href', '')
                    
                    # Asignar categoría basada en el título
                    category = categorize_product(title)
                    
                    products.append(Product(title=title, summary=summary, link=link, category=category))
                    
                return products
                
        except httpx.ReadTimeout:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error("Tiempo de espera agotado después de varios intentos")
                raise HTTPException(status_code=504, detail="Tiempo de espera agotado después de varios intentos")
            logger.debug(f"Timeout ocurrido, reintentando... ({retry_count}/{max_retries})")
            await asyncio.sleep(2 * retry_count)  # Espera progresiva entre reintentos
        except httpx.HTTPError as e:
            logger.error(f"Error HTTP: {e}")
            raise HTTPException(status_code=503, detail=f"Error al obtener datos del feed: {str(e)}")
        except Exception as e:
            logger.error(f"Error general: {e}")
            raise HTTPException(status_code=500, detail=f"Error al procesar los datos: {str(e)}")

# Endpoint para la página principal
@app.get("/")
async def root():
    return {
        "message": "Bienvenido a la API de Productos Comandato por Categorías", 
        "documentacion": "/docs",
        "endpoints_disponibles": [
            "/products/", 
            "/products/search/", 
            "/products/{index}",
            "/categories/",
            "/categories/{category_name}"
        ]
    }

# Endpoint para obtener todos los productos
@app.get("/products/", response_model=List[Product], tags=["productos"])
async def get_all_products():
    """
    Obtiene todos los productos disponibles en el feed de Comandato.
    """
    try:
        return await fetch_products()
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"message": "Servicio temporalmente no disponible. Por favor, inténtelo más tarde."}
        )

# Endpoint para buscar productos por término
@app.get("/products/search/", response_model=List[Product], tags=["productos"])
async def search_products(term: str):
    """
    Busca productos que contengan el término especificado en el título o resumen.
    
    - **term**: Término de búsqueda
    """
    try:
        products = await fetch_products()
        return [product for product in products 
                if term.lower() in product.title.lower() 
                or term.lower() in product.summary.lower()]
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"message": "Servicio temporalmente no disponible. Por favor, inténtelo más tarde."}
        )

# Endpoint para obtener un producto por su índice
@app.get("/products/{index}", response_model=Product, tags=["productos"])
async def get_product_by_index(index: int):
    """
    Obtiene un producto específico por su índice en la lista.
    
    - **index**: Índice del producto (comienza en 0)
    """
    try:
        products = await fetch_products()
        if 0 <= index < len(products):
            return products[index]
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"message": "Servicio temporalmente no disponible. Por favor, inténtelo más tarde."}
        )

# Endpoint para obtener todas las categorías disponibles
@app.get("/categories/", tags=["categorías"])
async def get_categories():
    """
    Obtiene todas las categorías disponibles de productos.
    """
    try:
        products = await fetch_products()
        categories = set(product.category for product in products)
        return {"categories": sorted(list(categories))}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"message": "Servicio temporalmente no disponible. Por favor, inténtelo más tarde."}
        )

# Endpoint para obtener productos por categoría
@app.get("/categories/{category_name}", response_model=List[Product], tags=["categorías"])
async def get_products_by_category(category_name: str):
    """
    Obtiene todos los productos de una categoría específica.
    
    - **category_name**: Nombre de la categoría
    """
    try:
        products = await fetch_products()
        category_products = [product for product in products if product.category.lower() == category_name.lower()]
        
        if not category_products:
            raise HTTPException(status_code=404, detail=f"No se encontraron productos en la categoría: {category_name}")
            
        return category_products
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"message": "Servicio temporalmente no disponible. Por favor, inténtelo más tarde."}
        )

# Punto de entrada para ejecutar la aplicación
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
