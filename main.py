import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

# GraphQL query to fetch user profile, stats, badges, and contest ranking
LEETCODE_QUERY = {
    "query": """
    query getUserProfile($username: String!) {
      matchedUser(username: $username) {
        username
        profile {
          ranking
          reputation
          starRating
          aboutMe
          userAvatar
          realName
          school
          company
          jobTitle
          countryName
          websites
          skillTags
        }
        badges {
          id
          name
          icon
        }
        submitStatsGlobal {
          acSubmissionNum { difficulty count submissions }
          totalSubmissionNum { difficulty count submissions }
        }
      }
      userContestRanking(username: $username) {
        rating
        ranking
        attendedContestsCount
        globalRanking
        totalParticipants
        topPercentage
      }
    }
    """,
    "variables": {"username": ""}
}


def fetch_leetcode_user(username: str) -> dict:
    payload = LEETCODE_QUERY.copy()
    payload["variables"] = {"username": username}

    try:
        r = requests.post(LEETCODE_GRAPHQL_URL, json=payload, timeout=12)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach LeetCode: {str(e)}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"LeetCode API error: HTTP {r.status_code}")

    data = r.json()
    if "errors" in data and data["errors"]:
        raise HTTPException(status_code=404, detail="User not found or LeetCode error")

    matched = data.get("data", {}).get("matchedUser")
    if not matched:
        raise HTTPException(status_code=404, detail="User not found")

    contest = data.get("data", {}).get("userContestRanking")

    # Shape a friendly response
    profile = matched.get("profile", {})

    # Build stats by difficulty
    ac_list = matched.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
    total_list = matched.get("submitStatsGlobal", {}).get("totalSubmissionNum", [])

    def by_diff(lst):
        return {item.get("difficulty", "All"): item for item in lst}

    ac_map = by_diff(ac_list)
    total_map = by_diff(total_list)

    stats = {}
    for diff in ["All", "Easy", "Medium", "Hard"]:
        ac = ac_map.get(diff, {}).get("count", 0)
        tot = total_map.get(diff, {}).get("count", 0)
        submissions = total_map.get(diff, {}).get("submissions", 0)
        acceptance = round((ac / tot * 100), 2) if tot else 0.0
        stats[diff.lower()] = {
            "solved": ac,
            "total": tot,
            "acceptanceRate": acceptance,
            "submissions": submissions,
        }

    result = {
        "username": matched.get("username"),
        "name": profile.get("realName") or matched.get("username"),
        "avatar": profile.get("userAvatar"),
        "ranking": profile.get("ranking"),
        "reputation": profile.get("reputation"),
        "starRating": profile.get("starRating"),
        "about": profile.get("aboutMe"),
        "company": profile.get("company"),
        "jobTitle": profile.get("jobTitle"),
        "school": profile.get("school"),
        "country": profile.get("countryName"),
        "websites": profile.get("websites") or [],
        "skills": profile.get("skillTags") or [],
        "badges": matched.get("badges") or [],
        "stats": stats,
        "contest": contest or None,
    }

    return result


@app.get("/api/leetcode/{username}")
def get_leetcode_user(username: str):
    """Fetch public LeetCode information for a username"""
    return fetch_leetcode_user(username)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
