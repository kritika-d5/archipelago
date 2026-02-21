import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import COMPOSIO_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])

COMPOSIO_ENTITY_ID = "mangobytes_default"


class ConnectUrlResponse(BaseModel):
    redirect_url: str
    toolkit: str


def get_composio():
    if not COMPOSIO_API_KEY:
        logger.info("COMPOSIO_API_KEY not set - GitHub/Notion OAuth unavailable")
        return None
    try:
        from composio import Composio
        return Composio(
            api_key=COMPOSIO_API_KEY,
            toolkit_versions={"github": "20260217_00", "notion": "20260217_00"}
        )
    except ImportError as e:
        logger.warning(f"composio package not installed: {e}")
        return None
    except Exception as e:
        logger.error(f"Composio init failed: {e}")
        return None


def _get_connect_url(composio, toolkit):
    callback = f"http://localhost:3000/connect-callback?toolkit={toolkit}"
    session = composio.create(user_id=COMPOSIO_ENTITY_ID, manage_connections=False)
    try:
        cr = session.authorize(toolkit, callback_url=callback)
    except TypeError:
        cr = session.authorize(toolkit)
    return cr.redirect_url


@router.get("/connect-url/{toolkit}")
async def get_connect_url(toolkit: str) -> ConnectUrlResponse:
    toolkit = toolkit.lower()
    if toolkit not in ("github", "notion", "slack"):
        raise HTTPException(status_code=400, detail="Invalid toolkit")
    composio = get_composio()
    if not composio:
        raise HTTPException(
            status_code=503,
            detail="Composio not configured. Add COMPOSIO_API_KEY to backend/.env and restart the server. Get a key at composio.dev"
        )
    try:
        url = _get_connect_url(composio, toolkit)
        return ConnectUrlResponse(redirect_url=url, toolkit=toolkit)
    except Exception as e:
        logger.error(f"Composio authorize failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _execute_tool(composio, slug, arguments):
    try:
        return composio.tools.execute(
            user_id=COMPOSIO_ENTITY_ID,
            slug=slug,
            arguments=arguments or {},
        )
    except Exception as e:
        raise e


@router.get("/github/repos")
async def list_github_repos():
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER",
            {"per_page": 100, "sort": "updated"},
        )
        data = result.get("data", result) if isinstance(result, dict) else result
        items = data if isinstance(data, list) else (data.get("repositories", []) if isinstance(data, dict) else [])
        if not isinstance(items, list):
            items = [data] if data else []
        repos = []
        for r in items or []:
            if isinstance(r, dict):
                owner = r.get("owner") or {}
                full_name = r.get("full_name") or f"{owner.get('login','')}/{r.get('name','')}"
                clone_url = r.get("clone_url") or r.get("html_url") or f"https://github.com/{full_name}.git"
                if full_name:
                    repos.append({"full_name": full_name, "clone_url": clone_url, "name": r.get("name", ""), "owner": owner})
            else:
                repos.append({"full_name": str(r), "clone_url": f"https://github.com/{r}.git", "name": str(r), "owner": {}})
        return {"repos": repos}
    except Exception as e:
        logger.error(f"List repos failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_org_list(items: list) -> list:
    orgs = []
    seen = set()
    for o in items or []:
        if isinstance(o, dict):
            login = (o.get("login") or o.get("org") or o.get("name") or "").strip()
            if login and login not in seen:
                seen.add(login)
                orgs.append({"login": login, "avatar_url": o.get("avatar_url", "") or o.get("avatarUrl", "")})
        elif isinstance(o, str) and o.strip() and o not in seen:
            seen.add(o)
            orgs.append({"login": o.strip(), "avatar_url": ""})
    return orgs


@router.get("/github/orgs")
async def list_github_orgs():
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    orgs = []
    try:
        result = _execute_tool(
            composio,
            "GITHUB_LIST_ORGANIZATIONS_FOR_THE_AUTHENTICATED_USER",
            {},
        )
        logger.info(f"Composio orgs raw keys: {list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
        data = result.get("data", result) if isinstance(result, dict) else result
        items = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("organizations") or data.get("items") or data.get("data") or data.get("body")
            if not items:
                for key in ("output", "response", "result", "value"):
                    v = data.get(key)
                    if isinstance(v, list):
                        items = v
                        break
        if isinstance(items, list):
            orgs = _normalize_org_list(items)
    except Exception as e:
        logger.warning(f"Composio list orgs failed: {e}", exc_info=True)

    if not orgs:
        try:
            repos_res = _execute_tool(
                composio,
                "GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER",
                {"per_page": 100, "sort": "updated"},
            )
            data = repos_res.get("data", repos_res) if isinstance(repos_res, dict) else repos_res
            repos = data if isinstance(data, list) else (data.get("repositories", []) or data.get("data", []) if isinstance(data, dict) else [])
            if isinstance(repos, list):
                for r in repos:
                    if not isinstance(r, dict):
                        continue
                    owner = r.get("owner") or {}
                    if isinstance(owner, dict):
                        login = owner.get("login", "")
                        if login and owner.get("type") == "Organization":
                            if not any(x["login"] == login for x in orgs):
                                orgs.append({"login": login, "avatar_url": owner.get("avatar_url", "")})
                    full_name = r.get("full_name", "")
                    if full_name and "/" in full_name:
                        org_login = full_name.split("/")[0]
                        if org_login and not any(x["login"] == org_login for x in orgs):
                            orgs.append({"login": org_login, "avatar_url": ""})
            orgs = _normalize_org_list([{"login": o["login"], "avatar_url": o.get("avatar_url", "")} for o in orgs])
        except Exception as e2:
            logger.warning(f"Fallback orgs from repos failed: {e2}")
    return {"organizations": orgs}


@router.get("/notion/pages")
async def list_notion_pages(query: str = ""):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "NOTION_FETCH_DATA",
            {"query": query, "fetch_type": "pages", "page_size": 50} if query else {"fetch_type": "pages", "page_size": 50},
        )
        data = result.get("data", result) if isinstance(result, dict) else result
        items = data if isinstance(data, list) else (data.get("results", []) or data.get("pages", []) or data.get("data", []) if isinstance(data, dict) else [])
        if not isinstance(items, list):
            items = [data] if data else []
        pages = []
        for p in items or []:
            if isinstance(p, dict):
                pid = p.get("id") or p.get("page_id", "")
                title = p.get("title", "")
                if not title and isinstance(p.get("properties"), dict):
                    title_prop = p["properties"].get("title") or p["properties"].get("Name") or {}
                    title_arr = title_prop.get("title", []) if isinstance(title_prop, dict) else []
                    if title_arr and isinstance(title_arr[0], dict):
                        title = title_arr[0].get("plain_text", "Untitled")
                if pid:
                    pages.append({"id": pid, "title": title or "Untitled", "url": p.get("url", "")})
            else:
                pages.append({"id": str(p), "title": "Untitled", "url": ""})
        return {"pages": pages}
    except Exception as e:
        logger.error(f"List Notion pages failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/page/{page_id:path}")
async def get_notion_page_content(page_id: str):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "NOTION_FETCH_ALL_BLOCK_CONTENTS",
            {"block_id": page_id, "recursive": True, "max_depth": 5},
        )
        data = result.get("data", result) if isinstance(result, dict) else result
        blocks = data if isinstance(data, list) else (data.get("results", []) or data.get("blocks", []) or data.get("children", []) if isinstance(data, dict) else [])
        if not isinstance(blocks, list):
            blocks = [data] if data else []
        text_parts = []

        def extract_text(block):
            if not isinstance(block, dict):
                return []
            out = []
            bt = block.get("type", "")
            content = block.get(bt, {}) or block.get("content", {})
            if isinstance(content, dict):
                rich = content.get("rich_text", []) or content.get("text", [])
                for r in (rich or []):
                    if isinstance(r, dict) and r.get("plain_text"):
                        out.append(r["plain_text"])
            elif isinstance(content, str):
                out.append(content)
            if not out and block.get("plain_text"):
                out.append(block["plain_text"])
            return out

        for b in blocks or []:
            text_parts.extend(extract_text(b))
            for child in b.get("children", []) if isinstance(b, dict) else []:
                text_parts.extend(extract_text(child))
        return {"content": "\n".join(text_parts) if text_parts else "", "page_id": page_id}
    except Exception as e:
        logger.error(f"Get Notion page failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notion/update")
async def update_notion_page(request: dict):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    page_id = request.get("page_id")
    content = request.get("content")
    if not page_id or not content:
        raise HTTPException(status_code=400, detail="page_id and content required")
    try:
        result = _execute_tool(
            composio,
            "NOTION_ADD_MULTIPLE_PAGE_CONTENT",
            {"parent_block_id": page_id, "content_blocks": [{"content": "[Suggested doc update] " + content[:2000], "block_property": "paragraph"}]},
        )
        return {
            "success": True,
            "result": result,
            "message": "Content added as a new paragraph at the bottom of your Notion page. Open the page in Notion to see it.",
            "notion_page_url": f"https://www.notion.so/{page_id.replace('-', '')}",
        }
    except Exception as e:
        logger.error(f"Update Notion page failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
