"""
Meta Insights API – Facebook Page, Instagram Business, (placeholder) Threads.
Uses long‑lived System User token and IDs from .env.
See workflows/meta_insights_setup.md.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GRAPH_VERSION = os.getenv("META_GRAPH_API_VERSION", "v18.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Set {name} in .env. See workflows/meta_insights_setup.md.")
    return value


def _graph_get(path: str, params: Optional[Dict] = None) -> Dict:
    token = _get_env("META_SYSTEM_USER_TOKEN")
    url = f"{GRAPH_BASE}{path}"
    p = {"access_token": token}
    if params:
        p.update(params)
    resp = requests.get(url, params=p, timeout=60)
    try:
        data = resp.json()
    except json.JSONDecodeError:
        raise SystemExit(f"Meta API error {resp.status_code}: {resp.text[:400]}")
    if resp.status_code != 200:
        # Meta errors are in JSON with 'error'
        raise SystemExit(f"Meta API error {resp.status_code}: {json.dumps(data, ensure_ascii=False)[:400]}")
    return data


def _parse_date(date_str: str) -> dt.date:
    return dt.datetime.strptime(date_str, "%Y-%m-%d").date()


def _date_params(
    since: Optional[str],
    until: Optional[str],
    date_preset: Optional[str],
) -> Dict[str, str]:
    if date_preset:
        return {"date_preset": date_preset}
    if since or until:
        if not since or not until:
            raise SystemExit("Use both --since and --until (YYYY-MM-DD) or --date-preset.")
        start = _parse_date(since)
        end = _parse_date(until)
        if end < start:
            raise SystemExit("--until must be >= --since.")
        # Graph API accepts yyyy-mm-dd or timestamps; use ISO dates.
        return {"since": start.isoformat(), "until": end.isoformat()}
    # default: today
    today = dt.date.today()
    return {"since": today.isoformat(), "until": today.isoformat()}


def page_insights(args: argparse.Namespace) -> None:
    page_id = _get_env("META_PAGE_ID")
    params = _date_params(args.since, args.until, args.date_preset)
    # Minimal, stable metrics; use /me?fields=insights with unsupported metrics sometimes fails by version.
    metrics = ["page_fans"]
    params["metric"] = ",".join(metrics)
    try:
        data = _graph_get(f"/{page_id}/insights", params)
    except SystemExit as e:
        # If metrics are not supported in your version, show a helpful message.
        raise SystemExit(
            f"{e}\nTry using --page-posts for per-post performance, or adjust metrics in meta_insights_api.py "
            "to ones listed as supported for your Page in the Meta docs."
        )
    rows = data.get("data", [])
    for m in rows:
        name = m.get("name")
        period = m.get("period")
        for point in m.get("values", []):
            end_time = point.get("end_time", "")
            value = point.get("value", "")
            print(f"{name}\t{period}\t{end_time}\t{value}")


def _flatten_post_insights(insights: List[Dict]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in insights:
        name = m.get("name")
        values = m.get("values") or []
        if not values:
            continue
        value = values[0].get("value")
        out[name] = str(value)
    return out


def page_posts(args: argparse.Namespace) -> None:
    page_id = _get_env("META_PAGE_ID")
    params = _date_params(args.since, args.until, args.date_preset)
    params.update(
        {
            "fields": "id,created_time,message",
            "limit": args.limit,
        }
    )
    posts = _graph_get(f"/{page_id}/posts", params).get("data", [])
    if not posts:
        print("No posts found for given date range.")
        return
    # Metrics confirmed as valid for this Page via --test-page-post-metrics.
    metric_list = [
        "post_impressions_unique",
        "post_clicks",
        "post_reactions_like_total",
    ]
    headers_printed = False
    for p in posts:
        post_id = p.get("id")
        created = p.get("created_time", "")
        message_raw = (p.get("message") or "").replace("\n", " ")[:80]
        # Windows console may not support all Unicode characters; strip non-ASCII for safety.
        try:
            message = message_raw.encode("ascii", "ignore").decode("ascii")
        except Exception:
            message = message_raw
        ins = _graph_get(f"/{post_id}/insights", {"metric": ",".join(metric_list)}).get("data", [])
        flat = _flatten_post_insights(ins)
        if not headers_printed:
            cols = ["post_id", "created_time", "message"] + metric_list
            print("\t".join(cols))
            headers_printed = True
        row = [post_id or "", created, message] + [flat.get(m, "") for m in metric_list]
        print("\t".join(row))


def ig_insights(args: argparse.Namespace) -> None:
    ig_id = _get_env("META_IG_BUSINESS_ID")
    params = _date_params(args.since, args.until, args.date_preset)
    # Use stable account-level metrics. Newer API requires metric_type=total_value for some metrics.
    # New API uses metric_type=total_value for some metrics; follower_count is separate.
    metrics = [
        "reach",
        "profile_views",
    ]
    params["metric"] = ",".join(metrics)
    params["metric_type"] = "total_value"
    params["period"] = "day"
    data = _graph_get(f"/{ig_id}/insights", params)
    for m in data.get("data", []):
        name = m.get("name")
        period = m.get("period")
        for point in m.get("values", []):
            value = point.get("value")
            end_time = point.get("end_time", "")
            print(f"{name}\t{period}\t{end_time}\t{value}")

    # Fetch follower_count as a separate lifetime metric (without metric_type constraint)
    try:
        fc = _graph_get(
            f"/{ig_id}/insights",
            {"metric": "follower_count", "period": "day"},
        )
        for m in fc.get("data", []):
            if m.get("name") != "follower_count":
                continue
            for point in m.get("values", []):
                value = point.get("value")
                end_time = point.get("end_time", "")
                print(f"follower_count\tday\t{end_time}\t{value}")
    except SystemExit:
        # If this fails, just skip follower_count rather than breaking the whole command.
        pass


def ig_media(args: argparse.Namespace) -> None:
    ig_id = _get_env("META_IG_BUSINESS_ID")
    params = {
        "fields": "id,caption,media_type,timestamp,permalink,like_count,comments_count",
        "limit": args.limit,
    }
    data = _graph_get(f"/{ig_id}/media", params)
    items = data.get("data", [])
    if not items:
        print("No media found.")
        return
    print("id\ttimestamp\tmedia_type\tlike_count\tcomments_count\tcaption\tpermalink")
    for m in items:
        row = [
            m.get("id", ""),
            m.get("timestamp", ""),
            m.get("media_type", ""),
            str(m.get("like_count", "")),
            str(m.get("comments_count", "")),
            (m.get("caption") or "").replace("\n", " ")[:80],
            m.get("permalink", ""),
        ]
        print("\t".join(row))


def threads_insights(_: argparse.Namespace) -> None:
    msg = (
        "Threads insights are not yet available via a stable public API. "
        "If Meta exposes Threads metrics via the Instagram Graph API for your account, "
        "you can usually access them through the IG endpoints already used by --ig-insights "
        "and --ig-media. Otherwise, manual export from Meta UI is required."
    )
    print(msg)


def test_ig_metrics(args: argparse.Namespace) -> None:
    ig_id = _get_env("META_IG_BUSINESS_ID")
    if not args.metric_list:
        raise SystemExit('Use --metric-list "metric1,metric2,..." with --test-ig-metrics')
    metrics = [m.strip() for m in args.metric_list.split(",") if m.strip()]
    params_base = _date_params(args.since, args.until, args.date_preset)
    # Insights API requires period; day is the most common.
    params_base.setdefault("period", "day")
    print("Testing IG metrics on account:", ig_id)
    for name in metrics:
        params = dict(params_base)
        params["metric"] = name
        try:
            data = _graph_get(f"/{ig_id}/insights", params)
            sample = data.get("data") or []
            has_values = bool(sample and sample[0].get("values"))
            print(f"OK\t{name}\tvalues:{'yes' if has_values else 'no'}")
        except SystemExit as e:
            msg = str(e).replace("\n", " ")[:160]
            print(f"FAIL\t{name}\t{msg}")


def test_page_post_metrics(args: argparse.Namespace) -> None:
    page_id = _get_env("META_PAGE_ID")
    if not args.metric_list:
        raise SystemExit('Use --metric-list "metric1,metric2,..." with --test-page-post-metrics')
    metrics = [m.strip() for m in args.metric_list.split(",") if m.strip()]
    posts = _graph_get(f"/{page_id}/posts", {"limit": 1}).get("data", [])
    if not posts:
        raise SystemExit("No posts found on Page; cannot test post metrics.")
    post_id = posts[0].get("id")
    print("Testing Page post metrics on post:", post_id)
    for name in metrics:
        try:
            data = _graph_get(f"/{post_id}/insights", {"metric": name})
            sample = data.get("data") or []
            has_values = bool(sample and sample[0].get("values"))
            print(f"OK\t{name}\tvalues:{'yes' if has_values else 'no'}")
        except SystemExit as e:
            msg = str(e).replace("\n", " ")[:160]
            print(f"FAIL\t{name}\t{msg}")


def ig_top_posts(args: argparse.Namespace) -> None:
    """
    List top IG posts over the last ~1 year by engagement and, when available, video views.
    Engagement is approximated as like_count + comments_count.
    """
    ig_id = _get_env("META_IG_BUSINESS_ID")
    # Cutoff: 365 days ago
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=365)

    fields = "id,caption,media_type,timestamp,permalink,like_count,comments_count"
    params = {
        "fields": fields,
        "limit": 50,
    }

    all_posts: List[Dict[str, object]] = []
    next_url: Optional[str] = None

    while True:
        if next_url:
            resp = requests.get(next_url, timeout=60)
            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise SystemExit(f"Meta API error {resp.status_code}: {resp.text[:400]}")
            if resp.status_code != 200:
                raise SystemExit(
                    f"Meta API error {resp.status_code}: {json.dumps(data, ensure_ascii=False)[:400]}"
                )
        else:
            data = _graph_get(f"/{ig_id}/media", params)

        items = data.get("data", [])
        if not items:
            break

        stop = False
        for m in items:
            ts_raw = m.get("timestamp")
            if not ts_raw:
                continue
            # Example format: 2025-02-10T12:34:56+0000 or 2025-02-10T12:34:56Z
            ts_str = str(ts_raw)
            if ts_str.endswith("Z"):
                ts_str = ts_str.replace("Z", "+00:00")
            try:
                ts = dt.datetime.fromisoformat(ts_str)
            except ValueError:
                # Fallback: ignore unparseable timestamps
                continue
            if ts.date() < cutoff:
                stop = True
                break

            like_count = int(m.get("like_count", 0) or 0)
            comments_count = int(m.get("comments_count", 0) or 0)
            engagement = like_count + comments_count

            # Try to fetch video views via media insights, but ignore failures.
            views = None
            media_type = m.get("media_type", "")
            if media_type in ("VIDEO", "REELS", "REEL"):
                try:
                    ins = _graph_get(
                        f"/{m.get('id')}/insights",
                        {"metric": "video_views"},
                    ).get("data", [])
                    if ins and ins[0].get("values"):
                        views_val = ins[0]["values"][0].get("value")
                        if isinstance(views_val, dict):
                            # Some metrics return {"value": <num>}
                            views_val = views_val.get("value")
                        views = int(views_val or 0)
                except SystemExit:
                    views = None

            all_posts.append(
                {
                    "id": m.get("id", ""),
                    "timestamp": ts.isoformat(),
                    "media_type": media_type or "",
                    "like_count": like_count,
                    "comments_count": comments_count,
                    "engagement": engagement,
                    "views": views if views is not None else 0,
                    "permalink": m.get("permalink", ""),
                    "caption": (m.get("caption") or "").replace("\n", " ")[:120],
                }
            )

        if stop:
            break

        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break

    if not all_posts:
        print("No media found in the last year.")
        return

    # Sort: primarily by engagement, then by views.
    all_posts.sort(key=lambda x: (x.get("engagement", 0), x.get("views", 0)), reverse=True)
    top_n = max(1, args.limit)
    top = all_posts[:top_n]

    print(
        "id\ttimestamp\tmedia_type\tlike_count\tcomments_count\tengagement\tviews\tpermalink\tcaption"
    )
    for p in top:
        # Windows console may not support all Unicode characters; strip non-ASCII for safety.
        caption_raw = str(p.get("caption", ""))
        try:
            caption = caption_raw.encode("ascii", "ignore").decode("ascii")
        except Exception:
            caption = caption_raw
        row = [
            str(p.get("id", "")),
            str(p.get("timestamp", "")),
            str(p.get("media_type", "")),
            str(p.get("like_count", "")),
            str(p.get("comments_count", "")),
            str(p.get("engagement", "")),
            str(p.get("views", "")),
            str(p.get("permalink", "")),
            caption,
        ]
        print("\t".join(row))


def main() -> int:
    parser = argparse.ArgumentParser(description="Meta Insights API – Facebook Page / IG / Threads (placeholder)")
    parser.add_argument("--page-insights", action="store_true", help="Page-level insights (reach, engaged users, etc.)")
    parser.add_argument("--page-posts", action="store_true", help="Per-post insights for Page posts")
    parser.add_argument("--ig-insights", action="store_true", help="IG account-level insights")
    parser.add_argument("--ig-media", action="store_true", help="Recent IG media with basic stats")
    parser.add_argument(
        "--ig-top-posts",
        action="store_true",
        help="List top IG posts over the last ~1 year by engagement and views.",
    )
    parser.add_argument("--threads-insights", action="store_true", help="Explain Threads insights support / limitations")
    parser.add_argument(
        "--test-ig-metrics",
        action="store_true",
        help="Test a comma-separated list of IG user insight metrics and report which ones work.",
    )
    parser.add_argument(
        "--test-page-post-metrics",
        action="store_true",
        help="Test a comma-separated list of Page post insight metrics on the most recent post.",
    )
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="Start date for insights")
    parser.add_argument("--until", metavar="YYYY-MM-DD", help="End date for insights")
    parser.add_argument(
        "--date-preset",
        choices=["today", "yesterday", "last_7d", "last_30d"],
        help="Use a preset date range instead of --since/--until",
    )
    parser.add_argument("-n", "--limit", type=int, default=20, help="Max number of posts/media to fetch")
    parser.add_argument(
        "--metric-list",
        help="Comma-separated list of metrics to use with --test-ig-metrics or --test-page-post-metrics.",
    )
    args = parser.parse_args()

    if not any(
        [
            args.page_insights,
            args.page_posts,
            args.ig_insights,
            args.ig_media,
            args.ig_top_posts,
            args.threads_insights,
            args.test_ig_metrics,
            args.test_page_post_metrics,
        ]
    ):
        parser.print_help()
        return 0

    if args.test_ig_metrics:
        test_ig_metrics(args)
        return 0

    if args.test_page_post_metrics:
        test_page_post_metrics(args)
        return 0

    if args.page_insights:
        page_insights(args)
    if args.page_posts:
        page_posts(args)
    if args.ig_insights:
        ig_insights(args)
    if args.ig_media:
        ig_media(args)
    if args.ig_top_posts:
        ig_top_posts(args)
    if args.threads_insights:
        threads_insights(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

