"""
🔗 ADVANCED ML LINT AGENT - WORKFLOW INTEGRATIONS
Ready-to-use integrations for modern development workflows

This script provides practical examples for integrating the Advanced ML Lint Agent
into various development workflows including Git hooks, CI/CD pipelines, IDEs,
and automated code review processes.
"""

import os
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from advanced_ml_lint_agent import AdvancedMLLintAgent

class WorkflowIntegrator:
    """Handles integration of ML Lint Agent into development workflows"""
    
    def __init__(self, config_path=None):
        self.agent = AdvancedMLLintAgent(config_path=config_path)
        self.integration_configs = self._load_integration_configs()
    
    def _load_integration_configs(self):
        """Load integration configurations"""
        return {
            "git_hooks": {
                "pre_commit": {
                    "enabled": True,
                    "blocking_issues": ["critical", "major"],
                    "max_issues": 10,
                    "timeout": 30
                },
                "pre_push": {
                    "enabled": False,
                    "full_project_scan": True,
                    "generate_report": True
                }
            },
            "ci_cd": {
                "fail_on_critical": True,
                "report_format": "junit",
                "artifact_reports": True,
                "notifications": ["slack", "email"]
            },
            "ide": {
                "real_time_analysis": True,
                "show_ml_reasoning": True,
                "auto_fix_suggestions": True
            }
        }

# ================================
# GIT HOOKS INTEGRATION
# ================================

def create_pre_commit_hook():
    """Create a pre-commit hook that uses the ML Lint Agent"""
    
    hook_script = '''#!/usr/bin/env python3
"""
Pre-commit hook using Advanced ML Lint Agent
Analyzes staged files for issues before commit
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the ML lint agent to path
sys.path.append(str(Path(__file__).parent.parent))

from advanced_ml_lint_agent import AdvancedMLLintAgent

def get_staged_python_files():
    """Get list of staged Python files"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True
        )
        files = result.stdout.strip().split('\n')
        return [f for f in files if f.endswith('.py') and os.path.exists(f)]
    except subprocess.CalledProcessError:
        return []

def main():
    """Main pre-commit hook function"""
    print("🤖 Running ML Lint Agent pre-commit analysis...")
    
    # Get staged files
    staged_files = get_staged_python_files()
    if not staged_files:
        print("✅ No Python files staged for commit")
        return 0
    
    # Initialize agent
    try:
        agent = AdvancedMLLintAgent()
    except Exception as e:
        print(f"❌ Failed to initialize ML Lint Agent: {e}")
        return 0  # Don't block commit on agent failure
    
    # Analyze staged files
    blocking_issues = []
    total_issues = 0
    
    for file_path in staged_files:
        print(f"  🔍 Analyzing: {file_path}")
        try:
            issues = agent.analyze_file_intelligent(file_path, developer_id="git_user")
            total_issues += len(issues)
            
            # Check for blocking issues
            critical_issues = [i for i in issues if i.severity in ["critical", "major"]]
            if critical_issues:
                blocking_issues.extend(critical_issues)
                
        except Exception as e:
            print(f"  ⚠️ Failed to analyze {file_path}: {e}")
    
    # Report results
    print(f"\n📊 Analysis complete: {total_issues} issues found in {len(staged_files)} files")
    
    if blocking_issues:
        print(f"\n🚨 COMMIT BLOCKED: {len(blocking_issues)} critical/major issues found:")
        for issue in blocking_issues[:5]:  # Show top 5
            print(f"  • {issue.file_path}:{issue.line_number} - {issue.title}")
            print(f"    {issue.description}")
        
        print(f"\n💡 Fix these issues before committing or use --no-verify to bypass")
        return 1  # Block commit
    
    if total_issues > 0:
        print(f"\n⚠️ {total_issues} minor issues found but not blocking commit")
        print("💡 Consider running full analysis: python -m advanced_ml_lint_agent .")
    
    print("✅ Commit approved by ML Lint Agent")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''
    
    # Write the hook
    hook_path = ".git/hooks/pre-commit"
    os.makedirs(os.path.dirname(hook_path), exist_ok=True)
    
    with open(hook_path, 'w') as f:
        f.write(hook_script)
    
    # Make executable
    os.chmod(hook_path, 0o755)
    
    print("✅ Pre-commit hook created successfully!")
    print(f"📁 Hook location: {hook_path}")
    print("🎯 The hook will analyze staged Python files before each commit")

def create_github_actions_workflow():
    """Create GitHub Actions workflow for ML lint analysis"""
    
    workflow_yaml = '''name: ML Lint Analysis

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  ml-lint:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install torch transformers
        pip install -r requirements.txt || echo "No requirements.txt found"
    
    - name: Download ML Model
      run: |
        # Add your model download logic here
        # For example, download from cloud storage or model registry
        echo "Downloading fine-tuned model..."
        # wget https://your-model-storage/codet5p-finetuned.tar.gz
        # tar -xzf codet5p-finetuned.tar.gz
    
    - name: Run ML Lint Analysis
      run: |
        python -m advanced_ml_lint_agent . --developer-id "ci_bot" --output "ml_lint_report.html"
      continue-on-error: false
    
    - name: Upload Analysis Report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: ml-lint-report
        path: ml_lint_report.html
    
    - name: Comment PR with Results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          
          // Read analysis summary (you'd implement this in the agent)
          let summary = "ML Lint Analysis Complete\\n";
          summary += "📊 Check the uploaded artifact for detailed results.";
          
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: summary
          });
'''
    
    # Create .github/workflows directory
    workflow_dir = ".github/workflows"
    os.makedirs(workflow_dir, exist_ok=True)
    
    workflow_path = os.path.join(workflow_dir, "ml-lint.yml")
    with open(workflow_path, 'w') as f:
        f.write(workflow_yaml)
    
    print("✅ GitHub Actions workflow created!")
    print(f"📁 Workflow location: {workflow_path}")
    print("🚀 Push to trigger ML lint analysis on GitHub")

# ================================
# IDE INTEGRATION
# ================================

def create_vscode_extension_settings():
    """Create VS Code settings for ML lint integration"""
    
    settings = {
        "python.linting.enabled": True,
        "python.linting.pylintEnabled": False,
        "ml_lint_agent.enabled": True,
        "ml_lint_agent.realTimeAnalysis": True,
        "ml_lint_agent.showMLReasoning": True,
        "ml_lint_agent.developerProfile": "default",
        "ml_lint_agent.confidenceThreshold": 0.6,
        "ml_lint_agent.autoFixSuggestions": True,
        "ml_lint_agent.notifications": {
            "critical": True,
            "major": True,
            "minor": False
        }
    }
    
    # Create .vscode directory
    vscode_dir = ".vscode"
    os.makedirs(vscode_dir, exist_ok=True)
    
    settings_path = os.path.join(vscode_dir, "settings.json")
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # Create tasks.json for running ML lint
    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "ML Lint: Analyze Current File",
                "type": "shell",
                "command": "python",
                "args": [
                    "-m", "advanced_ml_lint_agent",
                    "${file}",
                    "--developer-id", "${env:USER}",
                    "--output", "${workspaceFolder}/ml_lint_current.html"
                ],
                "group": "test",
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": False,
                    "panel": "shared"
                },
                "problemMatcher": []
            },
            {
                "label": "ML Lint: Analyze Project",
                "type": "shell", 
                "command": "python",
                "args": [
                    "-m", "advanced_ml_lint_agent",
                    "${workspaceFolder}",
                    "--developer-id", "${env:USER}",
                    "--output", "${workspaceFolder}/ml_lint_project.html"
                ],
                "group": "test",
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": False,
                    "panel": "shared"
                },
                "problemMatcher": []
            }
        ]
    }
    
    tasks_path = os.path.join(vscode_dir, "tasks.json")
    with open(tasks_path, 'w') as f:
        json.dump(tasks, f, indent=2)
    
    print("✅ VS Code integration created!")
    print(f"📁 Settings: {settings_path}")
    print(f"📁 Tasks: {tasks_path}")
    print("🎯 Use Ctrl+Shift+P > 'Tasks: Run Task' to run ML lint")

# ================================
# CI/CD INTEGRATION SCRIPTS
# ================================

def create_jenkins_pipeline():
    """Create Jenkins pipeline for ML lint analysis"""
    
    pipeline_script = """pipeline {
    agent any
    
    environment {
        PYTHON_VERSION = '3.9'
        ML_LINT_CONFIG = 'advanced_ml_lint_config.json'
    }
    
    stages {
        stage('Setup') {
            steps {
                echo 'Setting up ML Lint environment'
                sh '''
                    python -m venv ml_lint_env
                    source ml_lint_env/bin/activate
                    pip install torch transformers
                    pip install -r requirements.txt || echo "No requirements.txt"
                '''
            }
        }
        
        stage('Download Model') {
            steps {
                echo 'Downloading fine-tuned model'
                sh '''
                    # Add your model download logic
                    echo "Model download would happen here"
                '''
            }
        }
        
        stage('ML Lint Analysis') {
            steps {
                sh '''
                    source ml_lint_env/bin/activate
                    python -m advanced_ml_lint_agent . \\
                        --developer-id "jenkins_${BUILD_NUMBER}" \\
                        --output "ml_lint_report_${BUILD_NUMBER}.html"
                '''
            }
        }
        
        stage('Process Results') {
            steps {
                script {
                    // Parse results and set build status
                    def reportExists = fileExists("ml_lint_report_${BUILD_NUMBER}.html")
                    if (reportExists) {
                        echo "ML Lint analysis completed successfully"
                        archiveArtifacts artifacts: "ml_lint_report_${BUILD_NUMBER}.html"
                        publishHTML([
                            allowMissing: false,
                            alwaysLinkToLastBuild: true,
                            keepAll: true,
                            reportDir: '.',
                            reportFiles: "ml_lint_report_${BUILD_NUMBER}.html",
                            reportName: 'ML Lint Report'
                        ])
                    } else {
                        error("ML Lint analysis failed")
                    }
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        success {
            echo 'ML Lint analysis passed'
        }
        failure {
            echo 'ML Lint analysis failed'
            emailext (
                subject: "ML Lint Analysis Failed - ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "The ML Lint analysis failed. Please check the build logs.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
    }
}"""
    
    with open("Jenkinsfile", 'w') as f:
        f.write(pipeline_script)
    
    print("✅ Jenkins pipeline created!")
    print("📁 Pipeline: Jenkinsfile")
    print("🚀 Commit the Jenkinsfile to enable Jenkins CI")

# ================================
# CODE REVIEW INTEGRATION
# ================================

def create_code_review_bot():
    """Create a code review bot that uses ML lint analysis"""
    
    bot_script = """#!/usr/bin/env python3
\"\"\"
Automated Code Review Bot using ML Lint Agent
Integrates with GitHub/GitLab pull requests
\"\"\"

import sys
import os
import json
import requests
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from advanced_ml_lint_agent import AdvancedMLLintAgent

class CodeReviewBot:
    def __init__(self, repo_token, repo_url):
        self.agent = AdvancedMLLintAgent()
        self.token = repo_token
        self.repo_url = repo_url
    
    def review_pull_request(self, pr_number, changed_files):
        \"\"\"Review a pull request using ML analysis\"\"\"
        print(f"🤖 Reviewing PR #{pr_number}")
        
        all_issues = []
        review_comments = []
        
        for file_path in changed_files:
            if not file_path.endswith('.py'):
                continue
            
            print(f"  🔍 Analyzing: {file_path}")
            issues = self.agent.analyze_file_intelligent(
                file_path, 
                developer_id=f"review_bot_pr_{pr_number}"
            )
            all_issues.extend(issues)
            
            # Create review comments for significant issues
            for issue in issues:
                if issue.severity in ['critical', 'major']:
                    comment = self._create_review_comment(issue)
                    review_comments.append(comment)
        
        # Post review to GitHub/GitLab
        self._post_review(pr_number, review_comments, all_issues)
        
        return len(all_issues), len(review_comments)
    
    def _create_review_comment(self, issue):
        \"\"\"Create a review comment from an issue\"\"\"
        return {
            "path": issue.file_path,
            "line": issue.line_number,
            "body": f"**{issue.title}**\\n\\n"
                   f"{issue.description}\\n\\n"
                   f"**Suggested Fix:** {issue.suggested_fix}\\n\\n"
                   f"*Confidence: {issue.confidence:.1%} | "
                   f"ML Reasoning: {issue.ml_reasoning[:100]}...*"
        }
    
    def _post_review(self, pr_number, comments, all_issues):
        \"\"\"Post review to repository\"\"\"
        summary = self._generate_review_summary(all_issues)
        
        # This would integrate with GitHub/GitLab API
        print(f"\n📝 Review Summary for PR #{pr_number}:")
        print(summary)
        print(f"\n💬 Generated {len(comments)} review comments")

    def _generate_review_summary(self, issues):
        \"\"\"Generate a summary of the review\"\"\"
        if not issues:
            return "✅ No issues found by ML Lint Agent"
        
        severity_counts = {}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        
        summary = f"🤖 **ML Lint Analysis Results**\\n\\n"
        summary += f"📊 **Total Issues:** {len(issues)}\\n"
        
        for severity in ['critical', 'major', 'minor', 'suggestion']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                emoji = {'critical': '🔴', 'major': '🟡', 'minor': '🟢', 'suggestion': '💡'}
                summary += f"{emoji[severity]} **{severity.title()}:** {count}\\n"
        
        summary += f"\\n🧠 **ML-Powered Analysis:** Advanced AI model analyzed code for security, performance, and quality issues.\\n"
        summary += f"📈 **Confidence:** Average {sum(i.confidence for i in issues)/len(issues):.1%}\\n"
        
        return summary

def main():
    \"\"\"Main function for code review bot\"\"\"
    if len(sys.argv) < 3:
        print("Usage: python code_review_bot.py <pr_number> <file1,file2,...>")
        return 1
    
    pr_number = sys.argv[1]
    changed_files = sys.argv[2].split(',')
    
    bot = CodeReviewBot(
        repo_token=os.environ.get('GITHUB_TOKEN', ''),
        repo_url=os.environ.get('GITHUB_REPOSITORY', '')
    )
    
    issues_count, comments_count = bot.review_pull_request(pr_number, changed_files)
    
    print(f"\n✅ Review complete: {issues_count} issues, {comments_count} comments")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
    
    with open("code_review_bot.py", 'w') as f:
        f.write(bot_script)
    
    os.chmod("code_review_bot.py", 0o755)
    
    print("✅ Code review bot created!")
    print("📁 Bot script: code_review_bot.py")
    print("🤖 Integrate with GitHub Actions or webhooks")

# ================================
# DAILY WORKFLOW AUTOMATION
# ================================

def create_daily_analysis_script():
    """Create script for daily automated analysis"""
    
    daily_script = """#!/usr/bin/env python3
\"\"\"
Daily ML Lint Analysis
Automated daily code quality analysis and reporting
\"\"\"

import sys
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from advanced_ml_lint_agent import AdvancedMLLintAgent

def analyze_recent_changes(days=1):
    \"\"\"Analyze files changed in the last N days\"\"\"
    print(f"🔍 Analyzing changes from last {days} day(s)")
    
    # Get recently changed files (simplified - use git in practice)
    changed_files = []  # Would use: git diff --name-only HEAD~{days}
    
    # For demo, analyze all Python files
    for py_file in Path('.').rglob('*.py'):
        if not any(skip in str(py_file) for skip in ['.git', '__pycache__', '.venv']):
            changed_files.append(str(py_file))
    
    return changed_files[:10]  # Limit for demo

def generate_daily_report():
    \"\"\"Generate daily analysis report\"\"\"
    print("📊 Generating daily ML lint report...")
    
    agent = AdvancedMLLintAgent()
    changed_files = analyze_recent_changes()
    
    if not changed_files:
        print("✅ No recent changes to analyze")
        return None
    
    all_issues = []
    file_stats = {}
    
    for file_path in changed_files:
        try:
            issues = agent.analyze_file_intelligent(file_path, developer_id="daily_analysis")
            all_issues.extend(issues)
            file_stats[file_path] = len(issues)
            print(f"  📄 {file_path}: {len(issues)} issues")
        except Exception as e:
            print(f"  ❌ Failed to analyze {file_path}: {e}")
    
    # Generate report
    report = {
        "date": datetime.now().isoformat(),
        "files_analyzed": len(changed_files),
        "total_issues": len(all_issues),
        "severity_breakdown": {},
        "top_issues": [],
        "trends": {},
        "recommendations": []
    }
    
    # Calculate severity breakdown
    for issue in all_issues:
        severity = issue.severity
        report["severity_breakdown"][severity] = report["severity_breakdown"].get(severity, 0) + 1
    
    # Get top issues
    top_issues = sorted(all_issues, key=lambda x: x.priority_score, reverse=True)[:5]
    report["top_issues"] = [
        {
            "title": issue.title,
            "file": issue.file_path,
            "line": issue.line_number,
            "severity": issue.severity,
            "description": issue.description
        }
        for issue in top_issues
    ]
    
    # Add recommendations
    if report["severity_breakdown"].get("critical", 0) > 0:
        report["recommendations"].append("🚨 Address critical security issues immediately")
    
    if report["total_issues"] > 20:
        report["recommendations"].append("📈 Consider code refactoring session")
    
    if report["severity_breakdown"].get("performance", 0) > 5:
        report["recommendations"].append("⚡ Schedule performance optimization review")
    
    return report

def send_daily_email(report):
    \"\"\"Send daily report via email\"\"\"
    if not report:
        return
    
    # Email configuration (set environment variables)
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    email_user = os.environ.get('EMAIL_USER', '')
    email_pass = os.environ.get('EMAIL_PASS', '')
    recipient = os.environ.get('DAILY_REPORT_RECIPIENT', '')
    
    if not all([email_user, email_pass, recipient]):
        print("📧 Email not configured, printing report instead")
        print_report(report)
        return
    
    # Create email
    msg = MimeMultipart()
    msg['From'] = email_user
    msg['To'] = recipient
    msg['Subject'] = f"Daily ML Lint Report - {datetime.now().strftime('%Y-%m-%d')}"
    
    # Email body
    body = format_email_body(report)
    msg.attach(MimeText(body, 'html'))
    
    # Send email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        print(f"📧 Daily report sent to {recipient}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print_report(report)

def format_email_body(report):
    \"\"\"Format report as HTML email\"\"\"
    html = f\"\"\"
    <html>
    <body>
        <h2>🤖 Daily ML Lint Analysis Report</h2>
        <p><strong>Date:</strong> {report['date'][:10]}</p>
        
        <h3>📊 Summary</h3>
        <ul>
            <li>Files Analyzed: {report['files_analyzed']}</li>
            <li>Total Issues: {report['total_issues']}</li>
        </ul>
        
        <h3>⚠️ Severity Breakdown</h3>
        <ul>
    \"\"\"
    
    for severity, count in report['severity_breakdown'].items():
        emoji = {'critical': '🔴', 'major': '🟡', 'minor': '🟢', 'suggestion': '💡'}.get(severity, '📋')
        html += f"<li>{emoji} {severity.title()}: {count}</li>"
    
    html += \"\"\"
        </ul>
        
        <h3>🔍 Top Issues</h3>
        <ol>
    \"\"\"
    
    for issue in report['top_issues']:
        html += f\"\"\"
            <li>
                <strong>{issue['title']}</strong><br>
                📁 {issue['file']}:{issue['line']}<br>
                ⚠️ {issue['severity'].upper()}<br>
                📝 {issue['description']}<br><br>
            </li>
        \"\"\"
    
    html += \"\"\"
        </ol>
        
        <h3>💡 Recommendations</h3>
        <ul>
    \"\"\"
    
    for rec in report['recommendations']:
        html += f"<li>{rec}</li>"
    
    html += \"\"\"
        </ul>
        
        <p><em>Generated by Advanced ML Lint Agent</em></p>
    </body>
    </html>
    \"\"\"
    
    return html

def print_report(report):
    \"\"\"Print report to console\"\"\"
    print("\\n" + "="*50)
    print("📊 DAILY ML LINT ANALYSIS REPORT")
    print("="*50)
    print(f"📅 Date: {report['date'][:10]}")
    print(f"📄 Files Analyzed: {report['files_analyzed']}")
    print(f"🔍 Total Issues: {report['total_issues']}")
    
    print("\\n⚠️ Severity Breakdown:")
    for severity, count in report['severity_breakdown'].items():
        emoji = {'critical': '🔴', 'major': '🟡', 'minor': '🟢', 'suggestion': '💡'}.get(severity, '📋')
        print(f"  {emoji} {severity.title()}: {count}")
    
    print("\\n🏆 Top Issues:")
    for i, issue in enumerate(report['top_issues'], 1):
        print(f"  {i}. {issue['title']}")
        print(f"     📁 {issue['file']}:{issue['line']}")
        print(f"     ⚠️ {issue['severity'].upper()}")
    
    print("\\n💡 Recommendations:")
    for rec in report['recommendations']:
        print(f"  • {rec}")

def main():
    \"\"\"Main daily analysis function\"\"\"
    print("🌅 Starting daily ML lint analysis...")
    
    try:
        report = generate_daily_report()
        send_daily_email(report)
        print("✅ Daily analysis complete!")
    except Exception as e:
        print(f"❌ Daily analysis failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
    
    with open("daily_ml_analysis.py", 'w') as f:
        f.write(daily_script)
    
    os.chmod("daily_ml_analysis.py", 0o755)
    
    print("✅ Daily analysis script created!")
    print("📁 Script: daily_ml_analysis.py") 
    print("⏰ Schedule with cron: 0 9 * * * /path/to/daily_ml_analysis.py")

# ================================
# MAIN WORKFLOW INTEGRATION
# ================================

def main():
    """Main function to set up all workflow integrations"""
    print("🔗 ADVANCED ML LINT AGENT - WORKFLOW INTEGRATIONS")
    print("="*60)
    
    print("\nThis script will create integration files for:")
    print("  🔗 Git hooks (pre-commit)")
    print("  🚀 GitHub Actions workflow")
    print("  💻 VS Code integration")
    print("  🏗️ Jenkins pipeline")
    print("  🤖 Code review bot")
    print("  📊 Daily analysis automation")
    
    create_integrations = input("\n🎯 Create all integrations? (y/n): ").lower().startswith('y')
    
    if create_integrations:
        print("\n🔧 Creating workflow integrations...")
        
        try:
            create_pre_commit_hook()
            create_github_actions_workflow()
            create_vscode_extension_settings()
            create_jenkins_pipeline()
            create_code_review_bot()
            create_daily_analysis_script()
            
            print("\n✅ All workflow integrations created successfully!")
            print("\n📋 Next Steps:")
            print("  1. Commit the integration files to your repository")
            print("  2. Configure environment variables for notifications")
            print("  3. Set up model hosting/downloading for CI/CD")
            print("  4. Train your team on the new ML-powered workflow")
            print("\n🚀 Your development workflow is now ML-enhanced!")
            
        except Exception as e:
            print(f"❌ Failed to create integrations: {e}")
    
    else:
        print("\n🎯 Individual integration options:")
        print("  1. Git pre-commit hook")
        print("  2. GitHub Actions workflow")  
        print("  3. VS Code settings")
        print("  4. Jenkins pipeline")
        print("  5. Code review bot")
        print("  6. Daily analysis script")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            create_pre_commit_hook()
        elif choice == "2":
            create_github_actions_workflow()
        elif choice == "3":
            create_vscode_extension_settings()
        elif choice == "4":
            create_jenkins_pipeline()
        elif choice == "5":
            create_code_review_bot()
        elif choice == "6":
            create_daily_analysis_script()
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()
