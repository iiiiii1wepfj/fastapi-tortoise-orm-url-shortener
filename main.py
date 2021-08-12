from fastapi import FastAPI, Request, Form, APIRouter
from fastapi import __version__ as fastapi_version
from fastapi.responses import RedirectResponse, StreamingResponse, HTMLResponse

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
from user_agents import parse as parse_user_agent
from pkg_resources import get_distribution
from collections import Counter as collections_items_counter
from plotly import (
    graph_objects as plotlygraph_objects,
    io as plotlyio,
    __version__ as plotly_version,
)

try:
    from config import database_url, port
except:
    database_url = "sqlite://linksdb.sqlite"
    port = 8000
import uvicorn, re, sys, qrcode, os, jinja2, pydantic, httpx, pytz

app_version = "1.0"
min_slug_len = 4
max_slug_len = 30
max_auto_slug_len = 10
slug_allowed_characters = "abcdefghijklmnopqrstuvwxyz0123456789"
show_server_errors = False
httpxhttpsession = httpx.AsyncClient()

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
    stats: fields.ReverseRelation["LinkStats"]


class LinkStats(Model):
    slug: fields.ForeignKeyRelation[Links] = fields.ForeignKeyField(
        "models.Links", related_name="stats", pk=True
    )
    browser = fields.TextField()
    os = fields.TextField()
    country = fields.TextField(default="None", null=True)
    ref = fields.TextField(default="None", null=True)
    time = fields.DatetimeField(auto_now_add=True)


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
    pydantic_version_one = pydantic.version
    pydantic_version = pydantic_version_one.VERSION
    re_version = re.__version__
    qr_code_lib_version_one = get_distribution("qrcode")
    qr_code_lib_version = qr_code_lib_version_one.version
    httpx_version = httpx.__version__
    pytz_version = pytz.__version__
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
        f"plotly version: {plotly_version},\n"
        f"httpx version: {httpx_version},\n"
        f"pytz version: {pytz_version},\n"
        f"app pid: {app_pid}."
    )


@app.on_event("shutdown")
async def app_shutdown_actions():
    await httpxhttpsession.aclose()
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


async def get_the_client_ip(therequest):
    if "x-forwarded-for" in therequest.headers:
        the_client_ip = therequest.headers["x-forwarded-for"]
    else:
        the_client_ip = therequest.client.host
    return the_client_ip


async def get_geoip(ip):
    try:
        get_the_ip_location = await httpxhttpsession.get(f"https://api.country.is/{ip}")
    except:
        return "None"
    if not get_the_ip_location.is_error:
        thereqjson = get_the_ip_location.json()
        thecountry = thereqjson["country"]
        if thecountry != None:
            try:
                thecountry_code = thecountry.lower()
                thecountryname = pytz.country_names[thecountry_code]
            except:
                thecountryname = thecountry.lower()
            return thecountryname
        else:
            return "None"
    else:
        return "None"


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


async def redirect_link(slug: str, req):
    check_slug_exists = await link_exists(slug=slug)
    if not check_slug_exists:
        raise HTTPException(status_code=404, detail="the slug is not exists")
    else:
        check_link_db = await Links.get(slug=slug)
        theviews = int(check_link_db.views) + 1
        await Links.filter(slug=slug).update(views=theviews)
        try:
            parse_the_user_agent = parse_user_agent(req.headers["user-agent"])
            browser = parse_the_user_agent.browser.family.capitalize()
            os = parse_the_user_agent.os.family.capitalize()
            if "referer" in req.headers:
                req_ref = req.headers["referer"]
            else:
                req_ref = "None"
            try:
                get_the_client_ip_for_geoip = await get_the_client_ip(therequest=req)
                request_geoip_res = await get_geoip(ip=get_the_client_ip_for_geoip)
            except:
                request_geoip_res = "None"
            await LinkStats.create(
                slug=check_link_db,
                browser=browser,
                os=os,
                country=request_geoip_res,
                ref=req_ref,
            )
        except:
            pass
        return RedirectResponse(check_link_db.url)


async def get_clicks_stats_by_the_slug(slug: str):
    check_slug_exists = await link_exists(slug=slug)
    if not check_slug_exists:
        raise HTTPException(status_code=404, detail="the slug is not exists")
    else:
        get_click_stats = await LinkStats.filter(slug=slug)
        browser_count = collections_items_counter(i.browser for i in get_click_stats)
        os_count = collections_items_counter(i.os for i in get_click_stats)
        countries_count = collections_items_counter(i.country for i in get_click_stats)
        ref_count = collections_items_counter(i.ref for i in get_click_stats)
        all_count_stats = {
            "browsers": browser_count,
            "operating_systems": os_count,
            "countries": countries_count,
            "ref": ref_count,
        }
        return all_count_stats


async def get_links_count():
    get_all_links = await Links.all()
    get_all_links_count = get_all_links.count()
    return get_all_links_count


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


@app.get("/getclick_browser", include_in_schema=False)
async def getclickstatsbrowserpage(request: Request):
    return templates.TemplateResponse("stats.html", context={"request": request})


@app.post("/getclick_browser", include_in_schema=False)
async def getclickstatsbrowserpage_post(
    request: Request,
    slug: str = Form(...),
):
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    try:
        the_link_click_stats_get = await get_clicks_stats_by_the_slug(slug=theslug)
        reqjsonbrowsers = the_link_click_stats_get["browsers"]
        x = list(reqjsonbrowsers.keys())
        y = list(reqjsonbrowsers.values())

        thegraph_one = plotlygraph_objects.Figure(
            data=[
                plotlygraph_objects.Bar(
                    x=x,
                    y=y,
                    text=x,
                    textposition="auto",
                    marker=plotlygraph_objects.bar.Marker(
                        color=list(range(len(x))), colorscale="Viridis"
                    ),
                )
            ]
        )
        htmlgraph = plotlyio.to_html(
            thegraph_one,
            config={"displayModeBar": False},
            default_width="50%",
            default_height="50%",
        )
        return HTMLResponse(content=htmlgraph)
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


@app.get("/getclick_os", include_in_schema=False)
async def getclickstatsospage(request: Request):
    return templates.TemplateResponse("stats.html", context={"request": request})


@app.post("/getclick_os", include_in_schema=False)
async def getclickstatsospage_post(
    request: Request,
    slug: str = Form(...),
):
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    try:
        the_link_click_stats_get = await get_clicks_stats_by_the_slug(slug=theslug)
        reqjsonos = the_link_click_stats_get["operating_systems"]
        x = list(reqjsonos.keys())
        y = list(reqjsonos.values())

        thegraph_one = plotlygraph_objects.Figure(
            data=[
                plotlygraph_objects.Bar(
                    x=x,
                    y=y,
                    text=x,
                    textposition="auto",
                    marker=plotlygraph_objects.bar.Marker(
                        color=list(range(len(x))), colorscale="Viridis"
                    ),
                )
            ]
        )
        htmlgraph = plotlyio.to_html(
            thegraph_one,
            config={"displayModeBar": False},
            default_width="50%",
            default_height="50%",
        )
        return HTMLResponse(content=htmlgraph)
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


@app.get("/getclick_country", include_in_schema=False)
async def getclickstatsospage(request: Request):
    return templates.TemplateResponse("stats.html", context={"request": request})


@app.post("/getclick_country", include_in_schema=False)
async def getclickstatsospage_post(
    request: Request,
    slug: str = Form(...),
):
    if slug:
        theslug = slug.lower()
    else:
        theslug = None
    try:
        the_link_click_stats_get = await get_clicks_stats_by_the_slug(slug=theslug)
        reqjsonos = the_link_click_stats_get["countries"]
        x = list(reqjsonos.keys())
        y = list(reqjsonos.values())

        thegraph_one = plotlygraph_objects.Figure(
            data=[
                plotlygraph_objects.Bar(
                    x=x,
                    y=y,
                    text=x,
                    textposition="auto",
                    marker=plotlygraph_objects.bar.Marker(
                        color=list(range(len(x))), colorscale="Viridis"
                    ),
                )
            ]
        )
        htmlgraph = plotlyio.to_html(
            thegraph_one,
            config={"displayModeBar": False},
            default_width="50%",
            default_height="50%",
        )
        return HTMLResponse(content=htmlgraph)
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
    add_link_func_res = await add_link(
        url=url,
        slug=theslug,
        host=thehost,
    )
    return add_link_func_res


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
    get_link_func_res = await get_link(slug=theslug, host=thehost)
    return get_link_func_res


@apirouter.api_route("/click_stats", methods=["POST", "GET"])
async def get_slug_click_stats(slug: str):
    theslug = slug.lower()
    the_link_click_stats_get = await get_clicks_stats_by_the_slug(slug=theslug)
    return the_link_click_stats_get


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
async def redirect_to_the_url(slug: str, request: Request):
    theslug = slug.lower()
    return await redirect_link(slug=theslug, req=request)


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
