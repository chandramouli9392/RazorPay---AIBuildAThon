import json
import urllib.request

base_url = "http://127.0.0.1:8000"


def test_get(path):
    url = f"{base_url}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as res:
        content = res.read()
        print(f"[OK] GET {path} -> Status {res.status}")
        return content


def test_post(path, data=b"{}"):
    url = f"{base_url}{path}"
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        content = res.read()
        print(f"[OK] POST {path} -> Status {res.status}")
        return json.loads(content.decode("utf-8"))


def main():
    print("=" * 60)
    print("VERIFYING LOCAL FASTAPI ENDPOINTS & DASHBOARD")
    print("=" * 60)

    # 1. GET /
    dashboard = test_get("/")
    assert b"Razorpay AI Revenue Recovery Agent" in dashboard
    assert len(dashboard) > 50000
    assert b"app-layout" in dashboard
    assert b"chartComparison" in dashboard
    print("  -> Full Dashboard UI HTML loaded successfully (>50KB).")

    # 2. GET /docs
    docs = test_get("/docs")
    assert b"swagger" in docs.lower() or b"openapi" in docs.lower()
    print("  -> Swagger/OpenAPI docs loaded successfully.")

    # 3. GET /health
    health = json.loads(test_get("/health").decode("utf-8"))
    assert health["status"] == "ok"
    assert health["provider"] == "razorpay"
    print(f"  -> Health check: {health}")

    # 4. GET /recovery/metrics
    metrics = json.loads(test_get("/recovery/metrics").decode("utf-8"))
    assert "revenue_at_risk" in metrics
    assert "recovery_uplift_percent" in metrics
    print(
        f"  -> Metrics: Risk = INR {metrics['revenue_at_risk']:,}, "
        f"Uplift = {metrics['recovery_uplift_percent']}%"
    )

    # 5. POST /demo/simulate
    sim = test_post("/demo/simulate")
    assert sim["status"] == "success"
    print(
        f"  -> Demo Simulation: Risk = INR {sim['revenue_at_risk']:,}, "
        f"AI Recovered = INR {sim['actual_ai_recovered']:,}"
    )

    # 6. GET /recovery/cases
    cases = json.loads(test_get("/recovery/cases").decode("utf-8"))
    print(f"  -> Active Recovery Cases Queue: {len(cases.get('cases', []))} cases loaded.")

    # 7. POST /evaluation/run
    eval_res = test_post("/evaluation/run")
    assert eval_res["total_records"] == 5000
    print(
        f"  -> 5k Benchmark: F1 = {eval_res['f1_score_percent']}%, "
        f"AI Recovered = INR {eval_res['ai_recovered_inr']:,}"
    )

    print("=" * 60)
    print("ALL ENDPOINTS VERIFIED AND FUNCTIONING PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
