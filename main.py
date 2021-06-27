from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from tortoise import fields, Model
from tortoise.contrib.fastapi import register_tortoise
from typing import Optional
from secrets import choice
from random import randint
from loguru import logger
import uvicorn, re, sys

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


app = FastAPI()
slug_allowed_characters = "abcdefghijklmnopqrstuvwxyz0123456789"


class InvalidSlugError(Exception):
    pass


class SlugDosentExistsError(Exception):
    pass


class SlugAlreadyExistsError(Exception):
    pass


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


async def add_link(url: str, host, slug: Optional[str] = None):
    theslug = slug or await gen_calid_url_slug()
    for i in theslug:
        if not (i.isalpha()) and not (i.isdigit()):
            raise InvalidSlugError(
                f"invalid slug: {theslug}\nthe slug must to be english letters or number or both"
            )
    if len(theslug) < 4 or len(theslug) > 20:
        raise InvalidSlugError(
            f"invalid slug: {theslug}\nthe slug length must to be 4-20"
        )
    else:
        check_if_slug_exists = await link_exists(slug=slug)
        if not check_if_slug_exists:
            theurl = url if re.match(r"^https?://", url) else "http://" + url
            await Links.create(slug=theslug, url=theurl, views=0)
            return {"slug": theslug, "url": theurl, "link": f"{host}/{theslug}"}
        else:
            raise SlugAlreadyExistsError("the slug is already exists")


async def get_link(slug: str, host):
    check_slug_exists = await link_exists(slug=slug)
    if not check_slug_exists:
        raise SlugDosentExistsError("the slug is not exists")
    else:
        check_link_db = await Links.get(slug=slug)
        return {
            "slug": check_link_db.slug,
            "url": check_link_db.url,
            "link": f"{host}/{slug}",
            "views": check_link_db.views,
            "created_at": check_link_db.created_at,
            "last_change_at": check_link_db.last_db_change_at,
        }


async def redirect_link(slug: str):
    check_slug_exists = await link_exists(slug=slug)
    if not check_slug_exists:
        raise SlugDosentExistsError("the slug is not exists")
    else:
        check_link_db = await Links.get(slug=slug)
        theviews = int(check_link_db.views) + 1
        await Links.filter(slug=slug).update(views=theviews)
        return RedirectResponse(check_link_db.url)


async def get_links_count():
    return await Links.all().count()


@app.api_route("/add", methods=["POST", "GET"])
async def add_short_url(url: str, request: Request, slug: Optional[str] = None):
    thehost = request.headers["host"]
    theslug = slug.lower()
    return await add_link(url=url, slug=theslug, host=thehost)


@app.api_route("/get", methods=["POST", "GET"])
async def get_link_info(slug: str, request: Request):
    thehost = request.headers["host"]
    theslug = slug.lower()
    return await get_link(slug=theslug, host=thehost)


@app.api_route("/all", methods=["POST", "GET"])
async def get_the_links_count():
    return {"count": await get_links_count()}


@app.get("/{slug}")
async def redirect_to_the_url(slug: str):
    theslug = slug.lower()
    return await redirect_link(slug=theslug)


@app.exception_handler(500)
async def internal_server_error(request: Request, the_error: HTTPException):
    return JSONResponse(
        status_code=500,
        content={
            "error": f"{type(the_error).__name__}: {the_error}",
            "status_code": "500",
        },
    )


register_tortoise(
    app,
    db_url="sqlite://linksdb.sqlite",
    modules={"models": [__name__]},
    generate_schemas=True,
)
uvicorn.run(app=app, host="0.0.0.0", port=8000)
