#!/usr/bin/env python3
"""
Module 2: GitHub Actions Integration - STARTER CODE
Extend your PR Agent with webhook handling and MCP Prompts for CI/CD workflows.
"""

import json
import os
import subprocess
from typing import Optional
from pathlib import Path
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("pr-agent-actions")

# PR template directory (shared between starter and solution)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# Default PR templates
DEFAULT_TEMPLATES = {
    "bug.md": "Bug Fix",
    "feature.md": "Feature",
    "docs.md": "Documentation",
    "refactor.md": "Refactor",
    "test.md": "Test",
    "performance.md": "Performance",
    "security.md": "Security"
}

# File where webhook server stores events
EVENTS_FILE = Path(__file__).parent / "github_events.json"

# Type mapping for PR templates
TYPE_MAPPING = {
    "bug": "bug.md",
    "fix": "bug.md",
    "feature": "feature.md",
    "enhancement": "feature.md",
    "docs": "docs.md",
    "documentation": "docs.md",
    "refactor": "refactor.md",
    "cleanup": "refactor.md",
    "test": "test.md",
    "testing": "test.md",
    "performance": "performance.md",
    "optimization": "performance.md",
    "security": "security.md"
}


# ===== Module 1 Tools (Already includes output limiting fix from Module 1) =====

@mcp.tool()
async def analyze_file_changes(
    base_branch: str = "main",
    include_diff: bool = True,
    max_diff_lines: int = 500
) -> str:
    """Get the full diff and list of changed files in the current git repository.
    
    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
        max_diff_lines: Maximum number of diff lines to include (default: 500)
    """
    try:
        # Get list of changed files
        files_result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get diff statistics
        stat_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True
        )
        
        # Get the actual diff if requested
        diff_content = ""
        truncated = False
        if include_diff:
            diff_result = subprocess.run(
                ["git", "diff", f"{base_branch}...HEAD"],
                capture_output=True,
                text=True
            )
            diff_lines = diff_result.stdout.split('\n')
            
            # Check if we need to truncate (learned from Module 1)
            if len(diff_lines) > max_diff_lines:
                diff_content = '\n'.join(diff_lines[:max_diff_lines])
                diff_content += f"\n\n... Output truncated. Showing {max_diff_lines} of {len(diff_lines)} lines ..."
                diff_content += "\n... Use max_diff_lines parameter to see more ..."
                truncated = True
            else:
                diff_content = diff_result.stdout
        
        # Get commit messages for context
        commits_result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}..HEAD"],
            capture_output=True,
            text=True
        )
        
        analysis = {
            "base_branch": base_branch,
            "files_changed": files_result.stdout,
            "statistics": stat_result.stdout,
            "commits": commits_result.stdout,
            "diff": diff_content if include_diff else "Diff not included (set include_diff=true to see full diff)",
            "truncated": truncated,
            "total_diff_lines": len(diff_lines) if include_diff else 0
        }
        
        return json.dumps(analysis, indent=2)
        
    except subprocess.CalledProcessError as e:
        return json.dumps({"error": f"Git error: {e.stderr}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    templates = [
        {
            "filename": filename,
            "type": template_type,
            "content": (TEMPLATES_DIR / filename).read_text()
        }
        for filename, template_type in DEFAULT_TEMPLATES.items()
    ]
    
    return json.dumps(templates, indent=2)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.
    
    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    
    # Get available templates
    templates_response = await get_pr_templates()
    templates = json.loads(templates_response)
    
    # Find matching template
    template_file = TYPE_MAPPING.get(change_type.lower(), "feature.md")
    selected_template = next(
        (t for t in templates if t["filename"] == template_file),
        templates[0]  # Default to first template if no match
    )
    
    suggestion = {
        "recommended_template": selected_template,
        "reasoning": f"Based on your analysis: '{changes_summary}', this appears to be a {change_type} change.",
        "template_content": selected_template["content"],
        "usage_hint": "Claude can help you fill out this template based on the specific changes in your PR."
    }
    
    return json.dumps(suggestion, indent=2)


# ===== Module 2: New GitHub Actions Tools =====

@mcp.tool()
async def get_recent_actions_events(limit: int = 10) -> str:
    """Get recent GitHub Actions events received via webhook.
    
    Args:
        limit: Maximum number of events to return (default: 10)
    """
    # TODO: Implement this function
    # 1. Check if EVENTS_FILE exists
    if not EVENTS_FILE.exists():
        # 4. Return empty list if file doesn't exist
        return json.dumps([])

    # 2. Read the JSON file
    with open(EVENTS_FILE, "r") as f:
        events = json.load(f)

    # 3. Return the most recent events (up to limit)
    recent_events = sorted(events, key=lambda e: datetime.fromisoformat(e["received_at"]), reverse=True)[:limit]
    return json.dumps(recent_events, indent=2)

@mcp.tool()
async def get_workflow_status(workflow_name: Optional[str] = None) -> str:
    """Get the current status of GitHub Actions workflows.
    
    Args:
        workflow_name: Optional specific workflow name to filter by
    """
    # TODO: Implement this function
    # 1. Read events from EVENTS_FILE
    if not EVENTS_FILE.exists():
        return json.dumps({"message": "No GitHub Actions events received yet"})
    
    with open(EVENTS_FILE, 'r') as f:
        events = json.load(f)

    if not events:
        return json.dumps({"message": "No GitHub Actions events received yet"})
    
    # 2. Filter events for workflow_run events
    workflow_events = [
        e for e in events
        if e.get("workflow_run") is not None
    ]

    # 3. If workflow_name provided, filter by that name
    if workflow_name:
        workflow_events = [
            e for e in workflow_events
            if e["workflow_run"]["name"] == workflow_name
        ]

    # 4. Group by workflow and show latest status
    workflows = {}
    for event in workflow_events:
        run = event["workflow_run"]
        name = run["name"]
        if name not in workflows or run["updated_at"] > workflows[name]["updated_at"]:
            workflows[name] = {
                "name": name,
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "run_number": run["run_number"],
                "updated_at": run["updated_at"],
                "html_url": run["html_url"]
            }

    # 5. Return formatted workflow status information
    return json.dumps(list(workflows.values()), indent=2)
    
# ===== Module 2: MCP Prompts =====

@mcp.prompt()
async def analyze_ci_results():
    """Analyze recent CI/CD results and provide insights, including flaky tests."""
    return """Please analyze the recent CI/CD results from GitHub Actions:

1. Call get_recent_actions_events() to fetch the latest CI/CD events
2. Call get_workflow_status() to check current workflow states
3. Identify any failures or issues that need attention
4. Analyze test results across multiple runs to detect tests that:
   - Fail intermittently (flaky tests)
   - Frequently fail in recent runs
5. Provide actionable next steps based on the results

Format your response as:

## CI/CD Status Summary
- **Overall Health**: [Good/Warning/Critical]
- **Failed Workflows**: [List any failures with links]
- **Successful Workflows**: [List recent successes]
- **Flaky or Frequently Failing Tests**:
  - [List test names, frequency of failure, affected branches or workflows]
- **Recommendations**:
  - [Specific actions to take — e.g., isolate flaky tests, rerun strategy, improve stability]
- **Trends**:
  - [Any patterns or recurring issues you notice]
"""

@mcp.prompt()
async def generate_pr_status_report():
    """Generate a comprehensive PR status report including CI/CD results and flaky test analysis."""
    return """Generate a comprehensive PR status report:

1. Use analyze_file_changes() to understand what changed
2. Use get_workflow_status() to check CI/CD status
3. Use analyze_ci_results() to incorporate deeper insights into recent test runs
4. Identify any tests that:
   - Fail intermittently (flaky)
   - Fail frequently across recent runs
5. Use suggest_template() to recommend the appropriate PR template
6. Combine all information into a cohesive, actionable report

Create a detailed report with:

## 📋 PR Status Report

### 📝 Code Changes
- **Files Modified**: [Count by type - .py, .js, etc.]
- **Change Type**: [Feature/Bug/Refactor/etc.]
- **Impact Assessment**: [High/Medium/Low with reasoning]
- **Key Changes**: [Bullet points of main modifications]

### 🔄 CI/CD Status
- **All Checks**: [✅ Passing / ❌ Failing / ⏳ Running]
- **Test Results**: [Pass rate, failed tests if any]
- **Flaky or Frequently Failing Tests**:
  - [List test names, failure frequency, related workflows]
- **Build Status**: [Success/Failed with details]
- **Code Quality**: [Linting, coverage if available]

### 📌 Recommendations
- **Recommended Action**: [Specific actions to take — e.g., isolate flaky tests, rerun strategy, improve stability]

### ⚠️ Risks & Considerations
- [Any deployment risks]
- [Breaking changes]
- [Dependencies affected]

### 📈 Trends & Insights
- [Patterns in test failures or workflow instability]
- [Improvements or regressions since last PR]"""

@mcp.prompt()
async def troubleshoot_workflow_failure():
    """Help troubleshoot failing GitHub Actions workflows, including flaky test analysis and recurring patterns."""
    return """Help troubleshoot failing GitHub Actions workflows:

1. Use get_recent_actions_events() to identify recent workflow failures
2. Use get_workflow_status() to determine which workflows are failing and their current states
3. Analyze failure patterns and timing to detect:
   - Intermittent (flaky) failures
   - Consistent or recurring issues
4. Correlate failures with recent code changes (via analyze_file_changes())
5. Identify which tests, jobs, or steps are most frequently failing
6. Provide a structured troubleshooting guide with quick actions, deeper investigation steps, and preventive recommendations

Structure your response as:

## 🔧 Workflow Troubleshooting Guide

### ❌ Failed Workflow Details
- **Workflow Name**: [Name of failing workflow]
- **Failure Type**: [Test / Build / Deploy / Lint / Other]
- **First Failed**: [Timestamp or commit]
- **Failure Rate**: [Intermittent / Consistent / Increasing]
- **Affected Branches**: [List branches or PRs impacted]

### 🔍 Diagnostic Information
- **Error Patterns**: [Common stack traces, exit codes, or failure signatures]
- **Flaky or Frequently Failing Tests**:
  - [Test name, frequency, affected workflows]
- **Recent Changes**: [Relevant commits or files modified before failure]
- **Dependencies**: [External APIs, databases, or services potentially involved]

### 💡 Possible Causes (ordered by likelihood)
1. **[Most Likely]**: [Description + supporting evidence]
2. **[Likely]**: [Description + supporting evidence]
3. **[Possible]**: [Description + supporting evidence]

### ✅ Suggested Fixes
**Immediate Actions:**
- [ ] [Quick fix to try first — e.g., rerun failed job, clear cache, restart service]
- [ ] [Second quick fix if applicable]

**Investigation Steps:**
- [ ] [How to reproduce or isolate issue]
- [ ] [Logs, artifacts, or metrics to inspect]

**Long-term Solutions:**
- [ ] [Prevent recurrence — e.g., stabilize flaky test, refactor workflow step]
- [ ] [Improve reliability — e.g., add retries, timeouts, or monitoring]

### 📈 Trends & Insights
- [Recurring patterns across branches or time]
- [Flaky components or unstable dependencies]
- [Recent regression indicators]

### 📚 Resources
- [Relevant documentation links]
- [Similar historical issues or GitHub Discussions]
"""

if __name__ == "__main__":
    print("Starting PR Agent MCP server...")
    print("NOTE: Run webhook_server.py in a separate terminal to receive GitHub events")
    mcp.run()