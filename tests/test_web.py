"""Web module files are revalidated on every load, so a deploy shows up without a hard refresh."""


def test_web_files_are_not_cached_stale(client):
    for path in ("/", "/js/app.js", "/js/pages/sql.js"):
        res = client.get(path)
        assert res.status_code == 200
        assert res.headers["cache-control"] == "no-cache"
    # An unchanged file is still cheap: the ETag revalidation answers 304.
    etag = client.get("/js/app.js").headers["etag"]
    assert client.get("/js/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_sidebar_lists_the_sql_page(client):
    assert '"du-lieu-sql"' in client.get("/js/app.js").text
