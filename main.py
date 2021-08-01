from fastapi import FastAPI, Request, Form, APIRouter
from fastapi import __version__ as fastapi_version
from fastapi.responses import RedirectResponse, StreamingResponse

try:
    from fastapi.responses import ORJSONResponse as fastapijsonres
    from orjson import __version__ as orjson_version
except:
    from fastapi.responses import JSONResponse as fastapijsonres

    orjson_version = "not found"
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from starlette import __version__ as starlette_version
from tortoise import fields, Model
from tortoise.contrib.fastapi import register_tortoise
from tortoise import __version__ as tortoise_version
from typing import Optional
from secrets import choice
from random import randint
from loguru import logger
from loguru import __version__ as loguru_version
from io import BytesIO
from platform import python_version as get_python_version
from pkg_resources import get_distribution

try:
    from config import database_url, port
except:
    database_url = "sqlite://linksdb.sqlite"
    port = 8000
import uvicorn, re, sys, qrcode, os, jinja2, pydantic

app_version = "1.0"
min_slug_len = 4
max_slug_len = 30
max_auto_slug_len = 10
slug_allowed_characters = "abcdefghijklmnopqrstuvwxyz0123456789"
show_server_errors = False

logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | {level} | <level>{message}</level>",
)


class Links(Model):
    slug = fields.CharField(max_length=max_slug_len, pk=True)
    url = fields.TextField()
    views = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    last_db_change_at = fields.DatetimeField(auto_now=True)


app = FastAPI(
    docs_url=None,
    redoc_url=None,
    title="url shortener",
    description='the source code: <a href="https://github.com/iiiiii1wepfj/fastapi-tortoise-orm-url-shortener">https://github.com/iiiiii1wepfj/fastapi-tortoise-orm-url-shortener</a>, for donations: <a href="https://paypal.me/itayki">https://paypal.me/itayki</a>.',
    version=app_version,
)


@app.on_event("startup")
async def app_startup_actions():
    py_version = get_python_version()
    uvicorn_version = uvicorn.__version__
    jinja2_version = jinja2.__version__
    pydantic_version = pydantic.version.VERSION
    re_version = re.__version__
    qr_code_lib_version = get_distribution("qrcode").version
    app_pid = os.getpid()
    logger.info(
        "app started.\n"
        f"python version: {py_version},\n"
        f"app version: {app_version},\n"
        f"tortoise-orm version: {tortoise_version},\n"
        f"fastapi version: {fastapi_version},\n"
        f"starlette version: {starlette_version},\n"
        f"uvicorn version: {uvicorn_version},\n"
        f"jinja2 version: {jinja2_version},\n"
        f"orjson version: {orjson_version},\n"
        f"pydantic version: {pydantic_version},\n"
        f"re version: {re_version},\n"
        f"qrcode version: {qr_code_lib_version},\n"
        f"loguru version: {loguru_version},\n"
        f"app pid: {app_pid}."
    )


@app.on_event("shutdown")
async def app_shutdown_actions():
    logger.info(
        "app stopped, bye.",
    )


async def link_exists(slug: str):
    return await Links.exists(slug=slug)


def gen_url_slug():
    the_slug_length = randint(min_slug_len, max_auto_slug_len)
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
    if len(theslug) < min_slug_len or len(theslug) > max_slug_len:
        raise HTTPException(
            status_code=400,
            detail=f"invalid slug {theslug}: the slug length must to be {min_slug_len}-{max_slug_len}",
        )
    elif check_if_slug_exists:
        raise HTTPException(
            status_code=409,
            detail="the slug is already exists",
        )
    else:
        return True


async def add_link(
    url: str,
    host,
    slug: Optional[str] = None,
):
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
    request: Request,
    url: str = Form(...),
    slug: Optional[str] = Form(None),
):
    thehost = request.url.hostname
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    try:
        add_the_link = await add_link(
            url=url,
            slug=theslug,
            host=thehost,
        )
        result = add_the_link["link"]
        thetype = "the url"
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


@app.get("/docs", include_in_schema=False)
async def the_docs_swagger_url_page_web_plugin_func_swagger():
    the_openapi_url = app.openapi_url
    the_docs_title = app.title + " docs"
    return get_swagger_ui_html(
        openapi_url=the_openapi_url,
        title=the_docs_title,
    )


@app.get(path="/redoc", include_in_schema=False)
async def the_docs_redoc_url_page_web_plugin_func_swagger():
    the_openapi_url = app.openapi_url
    the_docs_title = app.title + " docs"
    return get_redoc_html(
        openapi_url=the_openapi_url,
        title=the_docs_title,
    )


@app.get("/get", include_in_schema=False)
async def statspage(request: Request):
    return templates.TemplateResponse("stats.html", context={"request": request})


@app.post("/get", include_in_schema=False)
async def statspage_post(
    request: Request,
    slug: str = Form(...),
):
    thehost = request.url.hostname
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


@apirouter.api_route(
    "/add",
    methods=[
        "POST",
        "GET",
    ],
    response_class=fastapijsonres,
)
async def add_short_url(
    url: str,
    request: Request,
    slug: Optional[str] = None,
):
    thehost = request.url.hostname
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    return await add_link(url=url, slug=theslug, host=thehost)


@apirouter.api_route(
    "/get",
    methods=[
        "POST",
        "GET",
    ],
    response_class=fastapijsonres,
)
async def get_link_info(slug: str, request: Request):
    thehost = request.url.hostname
    theslug = slug.lower()
    return await get_link(slug=theslug, host=thehost)


@apirouter.api_route(
    "/all",
    methods=[
        "POST",
        "GET",
    ],
    response_class=fastapijsonres,
)
async def get_the_links_count():
    return {"count": await get_links_count()}


@app.get("/{slug}")
async def redirect_to_the_url(slug: str):
    theslug = slug.lower()
    return await redirect_link(slug=theslug)


@app.api_route("/{slug}/qr", methods=["POST", "GET"])
async def generate_qr_code(slug: str, request: Request):
    thehost = request.url.hostname
    get_the_link_qr_code = await get_link_qr(slug=slug, host=thehost)
    return get_the_link_qr_code


@app.exception_handler(405)
async def method_not_allowed_error_handle(
    request: Request,
    the_error: HTTPException,
):
    request_http_method = request.method
    request_full_url = (
        f"{request.url.scheme}://{request.url.hostname}{request.url.path}"
    )
    return fastapijsonres(
        status_code=405,
        content={
            "error": f"the method {request_http_method} is not allowed for {request_full_url}.",
            "status_code": "405",
        },
    )


if show_server_errors:

    @app.exception_handler(500)
    async def internal_server_error(
        request: Request,
        the_error: HTTPException,
    ):
        return fastapijsonres(
            status_code=500,
            content={
                "error": f"{type(the_error).__name__}: {the_error}.",
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
