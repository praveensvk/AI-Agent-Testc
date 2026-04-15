"""Test crawl with login authentication."""
import asyncio
from app.services.crawler import crawl_page, crawl_pages


async def test():
    print("=" * 60)
    print("TEST 1: Crawl login page (no auth)")
    print("=" * 60)
    snap = await crawl_page("http://localhost:3005/login")
    print("Title:", snap.page_title)
    print("Elements:", len(snap.elements))
    for e in snap.elements[:10]:
        txt = (e.text or "")[:40]
        print(f"  [{e.element_type}] selector={e.selector} text={txt!r}")
    print("Forms:", len(snap.forms))

    print()
    print("=" * 60)
    print("TEST 2: Crawl protected page WITH auth")
    print("=" * 60)
    snap2 = await crawl_page(
        "http://localhost:3005/",
        login_url="http://localhost:3005/login",
        login_username="test@example.com",
        login_password="password123",
    )
    print("Title:", snap2.page_title)
    print("Elements:", len(snap2.elements))
    for e in snap2.elements[:15]:
        txt = (e.text or "")[:40]
        print(f"  [{e.element_type}] selector={e.selector} text={txt!r}")
    print("Forms:", len(snap2.forms))

    print()
    print("=" * 60)
    print("TEST 3: Crawl multiple pages WITH auth (shared session)")
    print("=" * 60)
    snaps = await crawl_pages(
        "http://localhost:3005",
        ["/", "/products", "/cart"],
        login_url="http://localhost:3005/login",
        login_username="test@example.com",
        login_password="password123",
    )
    for s in snaps:
        print(f"  {s.page_url}: title={s.page_title}, elements={len(s.elements)}, forms={len(s.forms)}")


asyncio.run(test())
