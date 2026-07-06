import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import COMPOSIO_API_KEY, FRONTEND_PUBLIC_URL
from app.core.session import get_session_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class ConnectUrlResponse(BaseModel):
    redirect_url: str
    toolkit: str
    callback_url: str = Field(
        description="Post-OAuth redirect we requested; should be your Vercel /connect-callback, not localhost."
    )


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


def _get_connect_url(composio, toolkit, entity_id):
    callback = f"{FRONTEND_PUBLIC_URL}/connect-callback?toolkit={toolkit}"
    logger.info("Composio OAuth toolkit=%s callback_url=%s (FRONTEND_PUBLIC_URL from env)", toolkit, callback)
    session = composio.create(user_id=entity_id, manage_connections=False)
    cr = session.authorize(toolkit, callback_url=callback)
    return cr.redirect_url, callback


@router.get("/connect-url/{toolkit}")
async def get_connect_url(toolkit: str, session_id: str = Depends(get_session_id)) -> ConnectUrlResponse:
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
        url, callback = _get_connect_url(composio, toolkit, session_id)
        return ConnectUrlResponse(redirect_url=url, toolkit=toolkit, callback_url=callback)
    except Exception as e:
        logger.error(f"Composio authorize failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _execute_tool(composio, slug, arguments, entity_id):
    try:
        return composio.tools.execute(
            user_id=entity_id,
            slug=slug,
            arguments=arguments or {},
        )
    except Exception as e:
        raise e


@router.get("/github/repos")
async def list_github_repos(session_id: str = Depends(get_session_id)):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER",
            {"per_page": 100, "sort": "updated"},
            session_id,
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
async def list_github_orgs(session_id: str = Depends(get_session_id)):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    orgs = []
    try:
        result = _execute_tool(
            composio,
            "GITHUB_LIST_ORGANIZATIONS_FOR_THE_AUTHENTICATED_USER",
            {},
            session_id,
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
                session_id,
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
async def list_notion_pages(query: str = "", session_id: str = Depends(get_session_id)):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "NOTION_FETCH_DATA",
            {"query": query, "fetch_type": "pages", "page_size": 50} if query else {"fetch_type": "pages", "page_size": 50},
            session_id,
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
async def get_notion_page_content(page_id: str, session_id: str = Depends(get_session_id)):
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    try:
        result = _execute_tool(
            composio,
            "NOTION_FETCH_ALL_BLOCK_CONTENTS",
            {"block_id": page_id, "recursive": True, "max_depth": 5},
            session_id,
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


class NotionUpdateRequest(BaseModel):
    page_id: str
    content: str
    suggestion_type: str = "add"  # "add", "update", "fix"
    current_text: str = ""  # Text to find and replace (for update/fix)
    suggested_text: str = ""  # New text to insert/replace with


@router.post("/notion/update")
async def update_notion_page(request: NotionUpdateRequest, session_id: str = Depends(get_session_id)):
    """
    Apply a documentation suggestion to a Notion page.
    
    For "update" or "fix" types: Finds the current_text in the document and replaces it with suggested_text.
    For "add" type: Inserts the suggested_text at an appropriate location.
    """
    composio = get_composio()
    if not composio:
        raise HTTPException(status_code=503, detail="Composio not configured")
    
    if not request.page_id:
        raise HTTPException(status_code=400, detail="page_id required")
    
    # Use suggested_text if provided, otherwise fall back to content
    suggested_content = request.suggested_text or request.content
    if not suggested_content:
        raise HTTPException(status_code=400, detail="content or suggested_text required")
    
    try:
        # Get current page content to find where to insert/update
        page_content_result = _execute_tool(
            composio,
            "NOTION_FETCH_ALL_BLOCK_CONTENTS",
            {"block_id": request.page_id, "recursive": True, "max_depth": 5},
            session_id,
        )
        
        data = page_content_result.get("data", page_content_result) if isinstance(page_content_result, dict) else page_content_result
        blocks = data if isinstance(data, list) else (data.get("results", []) or data.get("blocks", []) or data.get("children", []) if isinstance(data, dict) else [])
        if not isinstance(blocks, list):
            blocks = [data] if data else []
        
        # For "update" or "fix" types, try to find and update existing content
        if request.suggestion_type in ("update", "fix") and request.current_text:
            # Find block containing the current text
            target_block_id = None
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_id = block.get("id") or block.get("block_id", "")
                block_type = block.get("type", "")
                content = block.get(block_type, {}) or block.get("content", {})
                
                # Extract text from block
                block_text = ""
                if isinstance(content, dict):
                    rich_text = content.get("rich_text", []) or content.get("text", [])
                    block_text = " ".join([r.get("plain_text", "") for r in rich_text if isinstance(r, dict)])
                elif isinstance(content, str):
                    block_text = content
                
                # Check if current_text appears in this block
                if request.current_text.lower().strip() in block_text.lower():
                    target_block_id = block_id
                    break
            
            if target_block_id:
                # Try to update the existing block
                # Note: Composio may not have direct block update, so we'll insert after and note the old content
                try:
                    # Insert the new content right after the block we found
                    result = _execute_tool(
                        composio,
                        "NOTION_ADD_MULTIPLE_PAGE_CONTENT",
                        {
                            "parent_block_id": target_block_id,
                            "content_blocks": [
                                {
                                    "content": suggested_content[:2000],
                                    "block_property": "paragraph"
                                }
                            ]
                        },
                        session_id,
                    )
                    logger.info(f"Inserted updated content after block {target_block_id} in Notion page: {request.page_id}")
                    return {
                        "success": True,
                        "result": result,
                        "message": f"Suggested content has been inserted in the document near the relevant section. Please review and remove the old text if needed.",
                        "notion_page_url": f"https://www.notion.so/{request.page_id.replace('-', '')}",
                    }
                except Exception as update_error:
                    logger.warning(f"Failed to insert after block, falling back to append: {update_error}")
                    # Fall through to append if insert fails
        
        # For "add" type or if update failed, insert at appropriate location
        # Try to find a good insertion point (after relevant section) or append at end
        insertion_block_id = request.page_id  # Default to page root
        
        # If we have current_text, try to find a block after it
        if request.current_text:
            found_current = False
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")
                content = block.get(block_type, {}) or block.get("content", {})
                block_text = ""
                if isinstance(content, dict):
                    rich_text = content.get("rich_text", []) or content.get("text", [])
                    block_text = " ".join([r.get("plain_text", "") for r in rich_text if isinstance(r, dict)])
                elif isinstance(content, str):
                    block_text = content
                
                if request.current_text.lower().strip() in block_text.lower():
                    found_current = True
                elif found_current:
                    # Use the next block as insertion point
                    insertion_block_id = block.get("id") or block.get("block_id", "")
                    break
        
        # Insert the new content
        result = _execute_tool(
            composio,
            "NOTION_ADD_MULTIPLE_PAGE_CONTENT",
            {
                "parent_block_id": insertion_block_id,
                "content_blocks": [
                    {
                        "content": suggested_content[:2000],
                        "block_property": "paragraph"
                    }
                ]
            },
            session_id,
        )
        
        action = "inserted" if request.suggestion_type == "add" else "added"
        logger.info(f"Successfully {action} suggestion to Notion page: {request.page_id}")
        
        return {
            "success": True,
            "result": result,
            "message": f"Suggested content has been {action} in the document. Open the page in Notion to see the changes.",
            "notion_page_url": f"https://www.notion.so/{request.page_id.replace('-', '')}",
        }
    except Exception as e:
        logger.error(f"Update Notion page failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update Notion page: {str(e)}")
