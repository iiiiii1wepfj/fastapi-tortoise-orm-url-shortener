from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from tortoise import fields, Model
from tortoise.contrib.fastapi import register_tortoise
from typing import Optional
from secrets import choice
from random import randint
from loguru import logger
from io import BytesIO
from config import database_url, port
import uvicorn, re, sys, qrcode

logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | {level} | <level>{message}</level>",
)


class Links(Model):
    slug = fields.CharField(max_length=20, pk=True)
    url = fields.TextField()
    views = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    last_db_change_at = fields.DatetimeField(auto_now=True)


app = FastAPI(
    docs_url=None,
    title="url shortener",
    description="the source code: https://github.com/iiiiii1wepfj/fastapi-tortoise-orm-url-shortener, for donations: https://paypal.me/itayki.",
    version="1.0",
)
slug_allowed_characters = "abcdefghijklmnopqrstuvwxyz0123456789"
show_server_errors = False


async def link_exists(slug: str):
    return await Links.exists(slug=slug)


def gen_url_slug():
    the_slug_length = randint(4, 6)
    slug = "".join(choice(slug_allowed_characters) for i in range(the_slug_length))
    return slug


async def gen_valid_url_slug():
    while True:
        slug = gen_url_slug()
        check_slug = await link_exists(slug=slug)
        if not check_slug:
            break
    return slug


async def check_if_valid_slug(slug: str):
    theslug = slug.lower()
    check_if_slug_exists = await link_exists(slug=theslug)
    for i in theslug:
        if i not in slug_allowed_characters:
            raise HTTPException(
                status_code=400,
                detail=f"invalid slug {theslug}: the slug must to be english letters or number or both",
            )
    if len(theslug) < 4 or len(theslug) > 20:
        raise HTTPException(
            status_code=400,
            detail=f"invalid slug {theslug}: the slug length must to be 4-20",
        )
    elif check_if_slug_exists:
        raise HTTPException(status_code=409, detail="the slug is already exists")
    else:
        return True


async def add_link(url: str, host, slug: Optional[str] = None):
    theslug = slug or await gen_valid_url_slug()
    theslug = theslug.lower()
    await check_if_valid_slug(slug=theslug)
    theurl = url if re.match(r"^https?://", url) else "http://" + url
    await Links.create(slug=theslug, url=theurl, views=0)
    return {
        "slug": theslug,
        "url": theurl,
        "link": f"{host}/{theslug}",
        "qr_code": f"{host}/{theslug}/qr",
    }


async def get_link(slug: str, host):
    theslug = slug.lower()
    check_slug_exists = await link_exists(slug=theslug)
    if not check_slug_exists:
        raise HTTPException(status_code=404, detail="the slug is not exists")
    else:
        check_link_db = await Links.get(slug=theslug)
        return {
            "slug": check_link_db.slug,
            "url": check_link_db.url,
            "link": f"{host}/{theslug}",
            "views": check_link_db.views,
            "created_at": check_link_db.created_at,
            "last_change_at": check_link_db.last_db_change_at,
            "qr_code": f"{host}/{theslug}/qr",
        }


async def get_link_qr(slug: str, host):
    theslug = slug.lower()
    check_slug_exists = await link_exists(slug=theslug)
    if not check_slug_exists:
        raise HTTPException(status_code=404, detail="the slug is not exists")
    else:
        thelink = f"{host}/{theslug}"
        make_qr_code = qrcode.make(thelink)
        bytes_qr_code = BytesIO()
        make_qr_code.save(bytes_qr_code)
        qr_code_result = BytesIO(bytes_qr_code.getvalue())
        return StreamingResponse(qr_code_result, media_type="image/jpeg")


async def redirect_link(slug: str):
    check_slug_exists = await link_exists(slug=slug)
    if not check_slug_exists:
        raise HTTPException(status_code=404, detail="the slug is not exists")
    else:
        check_link_db = await Links.get(slug=slug)
        theviews = int(check_link_db.views) + 1
        await Links.filter(slug=slug).update(views=theviews)
        return RedirectResponse(check_link_db.url)


async def get_links_count():
    return await Links.all().count()


templates = Jinja2Templates(directory="templates")


@app.get("/", include_in_schema=False)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", context={"request": request})


@app.post("/", include_in_schema=False)
async def homepage_post(
    request: Request, url: str = Form(...), slug: Optional[str] = Form(None)
):
    thehost = request.headers["host"]
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    try:
        add_the_link = await add_link(url=url, slug=theslug, host=thehost)
        result = add_the_link["link"]
        thetype = "the url"
    except Exception as e:
        result = e
        thetype = type(e).__name__
        if thetype == "HTTPException":
            result = e.detail
    return templates.TemplateResponse(
        "results.html",
        context={"request": request, "type": thetype, "result": result},
    )


@app.get("/docs", include_in_schema=False)
async def the_docs_url_page_web_plugin_func_swagger():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=app.title + " docs")


@app.get("/get", include_in_schema=False)
async def statspage(request: Request):
    return templates.TemplateResponse("stats.html", context={"request": request})


@app.post("/get", include_in_schema=False)
async def statspage_post(request: Request, slug: str = Form(...)):
    thehost = request.headers["host"]
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    get_the_link = await get_link(slug=theslug, host=thehost)
    try:
        result = f"\nviews: {get_the_link['views']}, created at: {get_the_link['created_at']}, last time changed at: {get_the_link['last_change_at']}, qr code: {get_the_link['qr_code']}"
        thetype = f"the stats for the url {get_the_link['link']}"
    except Exception as e:
        result = e
        thetype = type(e).__name__
        if thetype == "HTTPException":
            result = e.detail
    return templates.TemplateResponse(
        "results.html",
        context={
            "request": request,
            "type": thetype,
            "result": result,
        },
    )


apirouter = APIRouter(prefix="/api")


@apirouter.api_route("/add", methods=["POST", "GET"])
async def add_short_url(url: str, request: Request, slug: Optional[str] = None):
    thehost = request.headers["host"]
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    return await add_link(url=url, slug=theslug, host=thehost)


@apirouter.api_route("/get", methods=["POST", "GET"])
async def get_link_info(slug: str, request: Request):
    thehost = request.headers["host"]
    theslug = slug.lower()
    return await get_link(slug=theslug, host=thehost)


@apirouter.api_route("/all", methods=["POST", "GET"])
async def get_the_links_count():
    return {"count": await get_links_count()}


@app.get("/{slug}")
async def redirect_to_the_url(slug: str):
    theslug = slug.lower()
    return await redirect_link(slug=theslug)


@app.api_route("/{slug}/qr", methods=["POST", "GET"])
async def generate_qr_code(slug: str, request: Request):
    thehost = request.headers["host"]
    get_the_link_qr_code = await get_link_qr(slug=slug, host=thehost)
    return get_the_link_qr_code


if show_server_errors:
    from fastapi.responses import JSONResponse

    @app.exception_handler(500)
    async def internal_server_error(request: Request, the_error: HTTPException):
        return JSONResponse(
            status_code=500,
            content={
                "error": f"{type(the_error).__name__}: {the_error}",
                "status_code": "500",
            },
        )


else:
    pass


app.include_router(apirouter)
register_tortoise(
    app,
    db_url=database_url,
    modules={"models": [__name__]},
    generate_schemas=True,
)
uvicorn.run(app=app, host="0.0.0.0", port=port)
