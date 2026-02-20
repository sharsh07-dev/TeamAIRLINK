from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class FixDetail(BaseModel):
    file_path: str
    error_type: str
    original_snippet: Optional[str] = ""
    patched_snippet: Optional[str] = ""
    tests_passed: bool
    line_number: Optional[int] = None
    commit_message: Optional[str] = None

class ScoringMetrics(BaseModel):
    base_score: float = 0.0
    speed_factor: float = 0.0
    fix_efficiency: float = 0.0
    regression_penalty: float = 0.0
    final_ci_score: float = 0.0

class RunResult(BaseModel):
    repo_url: str
    branch_name: str
    run_id: str
    total_failures: int = 0
    total_fixes: int = 0
    ci_status: str
    fixes: List[FixDetail] = []
    ci_timeline: List[Any] = []
    scoring: ScoringMetrics = ScoringMetrics()
    start_time: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    team_name: Optional[str] = None
    leader_name: Optional[str] = None

# Request models
class RunAgentRequest(BaseModel):
    repo_url: str
    branch_name: str
    team_name: str
    leader_name: str
