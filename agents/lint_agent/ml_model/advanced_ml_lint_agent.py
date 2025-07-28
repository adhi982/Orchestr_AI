"""
ADVANCED ML-INTEGRATED LINT AGENT
Next-generation code analysis using your fine-tuned CodeT5+ model

🚀 FEATURES:
- Intelligent multi-file context analysis
- Advanced learning from developer feedback
- Real-time code review suggestions
- Security & performance deep analysis
- Natural language explanations
- Automated refactoring suggestions
- Integration with development workflows
- Personalized coding style recommendations

This agent goes beyond traditional linting by using ML to understand
code context, learn from patterns, and provide intelligent suggestions.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os
import json
import ast
import hashlib
import re
import pickle
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, Counter
import threading
import time
import requests

# ================================
# ENHANCED DATA STRUCTURES
# ================================

@dataclass
class CodeIssue:
    """Enhanced code issue with ML insights"""
    id: str
    file_path: str
    line_number: int
    column: int
    issue_type: str
    severity: str
    title: str
    description: str
    explanation: str
    suggested_fix: str
    confidence: float
    ml_reasoning: str  # ML model's reasoning
    code_snippet: str
    context: str
    related_files: List[str]  # Files related to this issue
    learning_tags: List[str]  # Tags for learning
    fix_examples: List[str]  # Code examples
    references: List[str]
    timestamp: str
    priority_score: float = 0.0
    developer_notes: str = ""
    auto_fixable: bool = False
    suggestion: str = ""

@dataclass
class DeveloperProfile:
    """Enhanced developer profile for personalization"""
    id: str
    name: str
    experience_level: str  # 'beginner', 'intermediate', 'expert'
    preferred_style: Dict[str, Any]
    learning_goals: List[str]
    feedback_history: List[str]
    skill_areas: List[str]
    project_roles: List[str]
    last_active: str

@dataclass
class ProjectContext:
    """Project-wide context for intelligent analysis"""
    project_path: str
    project_type: str  # 'web', 'ml', 'api', 'cli', etc.
    dependencies: List[str]
    coding_standards: Dict[str, Any]
    security_requirements: List[str]
    performance_targets: Dict[str, Any]
    file_relationships: Dict[str, List[str]]
    common_patterns: List[str]

class AdvancedMLLintAgent:
    """
    🤖 Advanced ML-Powered Lint Agent
    
    Provides intelligent, context-aware, learning-based code analysis
    using your fine-tuned CodeT5+ model.
    """
    
    def __init__(self, model_path=None, config_path="./advanced_ml_lint_config.json"):
        """Initialize the Advanced ML Lint Agent"""
        print("🤖 Initializing Advanced ML-Integrated Lint Agent...")
        
        # Load the fine-tuned model
        self.model_path = model_path or self._find_model_path()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize ML components
        self._load_ml_model()
        
        # Initialize agent components
        self.config_path = config_path
        self.config = self._load_config()
        self._init_knowledge_database()
        self._init_learning_system()
        self._init_context_analyzer()
        
        print(f"✅ Advanced ML Lint Agent loaded on {self.device}")
        print(f"🧠 Knowledge entries: {len(self.knowledge_db)}")
        print(f"📊 Learning patterns: {self.learning_system['total_patterns']}")
        print(f"🔗 Context relationships: {len(self.context_analyzer['file_graph'])}")
    
    def _load_ml_model(self):
        """Load and optimize the fine-tuned model"""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_path, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        # Optimize for inference
        if hasattr(torch, 'compile'):
            self.model = torch.compile(self.model)
    
    def _find_model_path(self):
        """Auto-find the model path"""
        possible_paths = [
            "./models/codet5p-finetuned",
            "./codet5p-finetuned",
            "./checkpoints/codet5p-finetuned",
            "../models/codet5p-finetuned",
            "E:/Intel Fest/Fine Tune/checkpoints/codet5p-finetuned"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError("Fine-tuned model not found!")
    
    def _load_config(self):
        """Load enhanced configuration"""
        default_config = {
            "ml_analysis": {
                "max_tokens": 512,
                "temperature": 0.3,
                "confidence_threshold": 0.6,
                "context_window": 10,
                "batch_size": 4
            },
            "learning": {
                "feedback_weight": 0.7,
                "pattern_learning_rate": 0.1,
                "adaptation_threshold": 0.8,
                "min_feedback_count": 5
            },
            "personalization": {
                "experience_weights": {
                    "beginner": {"education": 1.5, "warnings": 1.2, "suggestions": 0.8},
                    "intermediate": {"education": 1.0, "warnings": 1.0, "suggestions": 1.0},
                    "expert": {"education": 0.5, "warnings": 0.8, "suggestions": 1.3}
                },
                "style_adaptation": True,
                "learning_recommendations": True
            },
            "security": {
                "scan_depth": "deep",
                "vulnerability_db": "updated",
                "custom_rules": []
            },
            "performance": {
                "optimization_level": "aggressive",
                "memory_analysis": True,
                "complexity_tracking": True
            }
        }
        
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        
        # Save default config
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def _init_knowledge_database(self):
        """Initialize enhanced knowledge database"""
        self.knowledge_db = {
            "security_patterns": [
                {
                    "pattern": r"eval\s*\(",
                    "type": "code_injection",
                    "severity": "critical",
                    "description": "eval() can execute arbitrary code",
                    "cwe": "CWE-94",
                    "fix_template": "Use ast.literal_eval() for safe evaluation",
                    "examples": ["ast.literal_eval(user_input)", "json.loads(user_input)"]
                },
                {
                    "pattern": r"subprocess\.call\s*\(.*shell\s*=\s*True",
                    "type": "shell_injection",
                    "severity": "critical", 
                    "description": "Shell injection vulnerability",
                    "cwe": "CWE-78",
                    "fix_template": "Use subprocess with array arguments",
                    "examples": ["subprocess.call(['ls', directory])", "subprocess.run(['git', 'status'])"]
                },
                {
                    "pattern": r"password\s*=\s*[\"'][^\"']+[\"']",
                    "type": "hardcoded_secret",
                    "severity": "major",
                    "description": "Hardcoded password detected",
                    "cwe": "CWE-798",
                    "fix_template": "Use environment variables or secure config",
                    "examples": ["os.environ.get('PASSWORD')", "config.get_secure('password')"]
                }
            ],
            "performance_patterns": [
                {
                    "pattern": r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(",
                    "type": "inefficient_loop",
                    "severity": "minor",
                    "description": "Use enumerate() instead of range(len())",
                    "impact": "O(n) to O(1) improvement",
                    "fix_template": "for i, item in enumerate(items):",
                    "examples": ["for i, item in enumerate(items):", "for item in items:"]
                },
                {
                    "pattern": r"\w+\s*\+=\s*\w+\s*\+.*in.*for",
                    "type": "string_concatenation",
                    "severity": "minor",
                    "description": "String concatenation in loop is inefficient",
                    "impact": "O(n²) to O(n) improvement",
                    "fix_template": "Use join() for string concatenation",
                    "examples": ["''.join(items)", "result = []; result.append(item)"]
                }
            ],
            "code_quality_patterns": [
                {
                    "pattern": r"def\s+\w+\s*\([^)]*,\s*[^)]*,\s*[^)]*,\s*[^)]*,\s*[^)]*,\s*[^)]*\)",
                    "type": "too_many_parameters", 
                    "severity": "minor",
                    "description": "Function has too many parameters",
                    "principle": "Single Responsibility Principle",
                    "fix_template": "Consider using a data class or splitting the function",
                    "examples": ["@dataclass\\nclass Parameters:", "def process(config: Config):"]
                }
            ]
        }
    
    def _init_learning_system(self):
        """Initialize advanced learning system"""
        self.learning_system = {
            "feedback_db": self._load_feedback_database(),
            "pattern_weights": defaultdict(float),
            "developer_preferences": defaultdict(dict),
            "adaptation_rules": [],
            "success_patterns": [],
            "total_patterns": 0
        }
        
        # Load existing learning data
        if os.path.exists("learning_data.pkl"):
            with open("learning_data.pkl", 'rb') as f:
                saved_data = pickle.load(f)
                self.learning_system.update(saved_data)
        
        self.learning_system["total_patterns"] = sum(len(patterns) for patterns in self.knowledge_db.values())
    
    def _init_context_analyzer(self):
        """Initialize context analysis system"""
        self.context_analyzer = {
            "file_graph": defaultdict(list),
            "import_map": defaultdict(set),
            "function_calls": defaultdict(list),
            "class_hierarchy": defaultdict(list),
            "code_patterns": defaultdict(int)
        }
    
    def _load_feedback_database(self):
        """Load feedback from SQLite database"""
        db_path = "ml_lint_feedback.db"
        conn = sqlite3.connect(db_path)
        
        # Create tables if they don't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                issue_id TEXT,
                developer_id TEXT,
                action TEXT,
                feedback TEXT,
                timestamp TEXT,
                issue_type TEXT,
                confidence REAL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY,
                pattern TEXT,
                success_rate REAL,
                usage_count INTEGER,
                last_updated TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
        return db_path
    
    def analyze_file_intelligent(self, file_path: str, developer_id: str = "default", project_context: Optional[ProjectContext] = None) -> List[CodeIssue]:
        """
        🧠 Intelligent file analysis with ML and context awareness
        
        Args:
            file_path: Path to file to analyze
            developer_id: Developer ID for personalization
            project_context: Project context for better analysis
            
        Returns:
            List of intelligently analyzed code issues
        """
        print(f"🧠 Performing intelligent analysis: {file_path}")
        
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code_content = f.read()
        
        issues = []
        
        # 1. Multi-layered ML Analysis
        print("  🔍 ML-powered deep analysis...")
        ml_issues = self._deep_ml_analysis(file_path, code_content, project_context)
        issues.extend(ml_issues)
        
        # 2. Context-aware pattern analysis
        print("  🔗 Context-aware pattern analysis...")
        context_issues = self._context_aware_analysis(file_path, code_content, project_context)
        issues.extend(context_issues)
        
        # 3. Security deep scan
        print("  🔒 Security deep scan...")
        security_issues = self._advanced_security_analysis(file_path, code_content)
        issues.extend(security_issues)
        
        # 4. Performance optimization analysis
        print("  ⚡ Performance optimization analysis...")
        perf_issues = self._advanced_performance_analysis(file_path, code_content)
        issues.extend(perf_issues)
        
        # 5. Learning-based refinement
        print("  📚 Learning-based refinement...")
        refined_issues = self._apply_learning_refinement(issues, developer_id)
        
        # 6. Intelligent prioritization
        print("  🎯 Intelligent prioritization...")
        prioritized_issues = self._intelligent_prioritization(refined_issues, developer_id, project_context)
        
        print(f"✅ Intelligent analysis complete: {len(prioritized_issues)} issues")
        return prioritized_issues
    
    def _deep_ml_analysis(self, file_path: str, code: str, project_context: Optional[ProjectContext]) -> List[CodeIssue]:
        """Advanced ML analysis with multiple prompts and techniques"""
        issues = []
        
        # Analyze in chunks for better context
        code_chunks = self._smart_chunk_code(code)
        
        for chunk_idx, chunk in enumerate(code_chunks):
            # 1. General code review
            review_issues = self._ml_code_review(file_path, chunk, chunk_idx)
            issues.extend(review_issues)
            
            # 2. Architecture analysis
            arch_issues = self._ml_architecture_analysis(file_path, chunk, project_context)
            issues.extend(arch_issues)
            
            # 3. Bug prediction
            bug_issues = self._ml_bug_prediction(file_path, chunk)
            issues.extend(bug_issues)
        
        return issues
    
    def _ml_code_review(self, file_path: str, code: str, chunk_idx: int) -> List[CodeIssue]:
        """ML-powered code review"""
        issues = []
        
        review_prompts = [
            f"Review this code for bugs, issues, and improvements:\\n{code}",
            f"Analyze this code for potential problems and suggest fixes:\\n{code}",
            f"What are the main issues in this code? Provide specific suggestions:\\n{code}"
        ]
        
        for prompt_idx, prompt in enumerate(review_prompts):
            try:
                # Use ML model for analysis
                inputs = self.tokenizer(
                    prompt, 
                    return_tensors="pt", 
                    max_length=self.config["ml_analysis"]["max_tokens"], 
                    truncation=True,
                    padding=True
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=200,
                        temperature=self.config["ml_analysis"]["temperature"],
                        do_sample=True,
                        repetition_penalty=1.2,
                        pad_token_id=self.tokenizer.pad_token_id
                    )
                
                result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                analysis = result.split(prompt)[-1].strip()
                
                # Parse ML analysis into structured issues
                parsed_issues = self._parse_ml_review_output(file_path, code, analysis, chunk_idx)
                issues.extend(parsed_issues)
                
            except Exception as e:
                print(f"  ⚠️ ML review failed for chunk {chunk_idx}: {e}")
        
        return issues
    
    def _ml_architecture_analysis(self, file_path: str, code: str, project_context: Optional[ProjectContext]) -> List[CodeIssue]:
        """ML analysis for architectural issues"""
        if not project_context:
            return []
        
        context_prompt = f"""
        Analyze this code for architectural issues in a {project_context.project_type} project:
        Project dependencies: {', '.join(project_context.dependencies[:5])}
        Code to analyze:
        {code}
        
        Focus on: design patterns, SOLID principles, maintainability, scalability.
        """
        
        try:
            inputs = self.tokenizer(context_prompt, return_tensors="pt", max_length=400, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=150,
                    temperature=0.4,
                    do_sample=True
                )
            
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            analysis = result.split("Focus on:")[-1].strip()
            
            # Create architectural issue if significant problems found
            if any(word in analysis.lower() for word in ["violate", "poor", "anti-pattern", "coupling", "cohesion"]):
                issue = CodeIssue(
                    id=self._generate_issue_id(file_path, 1, "architecture"),
                    file_path=file_path,
                    line_number=1,
                    column=0,
                    issue_type="architecture",
                    severity="major",
                    title="Architectural Design Issue",
                    description="ML detected potential architectural problems",
                    explanation=f"Architectural analysis: {analysis}",
                    suggested_fix=self._generate_architectural_fix(analysis),
                    confidence=0.8,
                    ml_reasoning=analysis,
                    code_snippet=code[:200] + "...",
                    context="Architectural analysis",
                    related_files=[],
                    learning_tags=["architecture", "design", "ml-detected"],
                    fix_examples=[],
                    references=["https://refactoring.guru/design-patterns"],
                    timestamp=datetime.now().isoformat(),
                    auto_fixable=False
                )
                return [issue]
        
        except Exception as e:
            print(f"  ⚠️ Architecture analysis failed: {e}")
        
        return []
    
    def _ml_bug_prediction(self, file_path: str, code: str) -> List[CodeIssue]:
        """ML-based bug prediction"""
        bug_patterns = [
            "potential null pointer",
            "resource leak", 
            "race condition",
            "infinite loop",
            "memory leak",
            "deadlock"
        ]
        
        bug_prompt = f"Predict potential bugs in this code:\\n{code}"
        
        try:
            inputs = self.tokenizer(bug_prompt, return_tensors="pt", max_length=400, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=120,
                    temperature=0.3,
                    do_sample=True
                )
            
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            prediction = result.split("Predict potential bugs in this code:")[-1].strip()
            
            # Check if serious bugs are predicted
            if any(pattern in prediction.lower() for pattern in bug_patterns):
                issue = CodeIssue(
                    id=self._generate_issue_id(file_path, 1, "bug_prediction"),
                    file_path=file_path,
                    line_number=1,
                    column=0,
                    issue_type="bug_risk",
                    severity="major",
                    title="Potential Bug Detected",
                    description="ML model predicts potential bugs",
                    explanation=f"Bug prediction: {prediction}",
                    suggested_fix="Review code carefully for the predicted issues",
                    confidence=0.75,
                    ml_reasoning=prediction,
                    code_snippet=code[:200] + "...",
                    context="ML bug prediction",
                    related_files=[],
                    learning_tags=["bug-prediction", "ml-detected"],
                    fix_examples=[],
                    references=["https://docs.python.org/3/tutorial/errors.html"],
                    timestamp=datetime.now().isoformat(),
                    auto_fixable=False
                )
                return [issue]
        
        except Exception as e:
            print(f"  ⚠️ Bug prediction failed: {e}")
        
        return []
    
    def _context_aware_analysis(self, file_path: str, code: str, project_context: Optional[ProjectContext]) -> List[CodeIssue]:
        """Context-aware analysis using project knowledge"""
        issues = []
        
        # Build file context
        self._update_file_context(file_path, code)
        
        # Analyze imports
        import_issues = self._analyze_imports_intelligent(file_path, code, project_context)
        issues.extend(import_issues)
        
        # Analyze function relationships
        relationship_issues = self._analyze_function_relationships(file_path, code)
        issues.extend(relationship_issues)
        
        # Analyze consistency with project patterns
        consistency_issues = self._analyze_project_consistency(file_path, code, project_context)
        issues.extend(consistency_issues)
        
        return issues
    
    def _advanced_security_analysis(self, file_path: str, code: str) -> List[CodeIssue]:
        """Advanced security analysis with ML enhancement"""
        issues = []
        
        # Pattern-based security scanning
        for pattern_info in self.knowledge_db["security_patterns"]:
            pattern_issues = self._find_security_pattern_issues(file_path, code, pattern_info)
            issues.extend(pattern_issues)
        
        # ML-enhanced security analysis
        security_prompt = f"""
        Perform a comprehensive security analysis of this code.
        Look for: SQL injection, XSS, CSRF, authentication issues, authorization problems,
        input validation issues, cryptographic weaknesses, and other vulnerabilities.
        
        Code:
        {code[:800]}
        """
        
        try:
            inputs = self.tokenizer(security_prompt, return_tensors="pt", max_length=450, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=180,
                    temperature=0.2,
                    do_sample=True
                )
            
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            security_analysis = result.split("Code:")[-1].strip()
            
            # Parse security findings
            security_issues = self._parse_security_analysis(file_path, code, security_analysis)
            issues.extend(security_issues)
            
        except Exception as e:
            print(f"  ⚠️ Advanced security analysis failed: {e}")
        
        return issues
    
    def _advanced_performance_analysis(self, file_path: str, code: str) -> List[CodeIssue]:
        """Advanced performance analysis with optimization suggestions"""
        issues = []
        
        # Pattern-based performance analysis
        for pattern_info in self.knowledge_db["performance_patterns"]:
            perf_issues = self._find_performance_pattern_issues(file_path, code, pattern_info)
            issues.extend(perf_issues)
        
        # ML-enhanced performance analysis
        perf_prompt = f"""
        Analyze this code for performance optimizations.
        Focus on: algorithmic complexity, memory usage, I/O operations, 
        database queries, caching opportunities, and bottlenecks.
        
        Code:
        {code[:800]}
        """
        
        try:
            inputs = self.tokenizer(perf_prompt, return_tensors="pt", max_length=450, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=160,
                    temperature=0.4,
                    do_sample=True
                )
            
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            perf_analysis = result.split("Code:")[-1].strip()
            
            # Parse performance findings
            perf_issues = self._parse_performance_analysis(file_path, code, perf_analysis)
            issues.extend(perf_issues)
            
        except Exception as e:
            print(f"  ⚠️ Advanced performance analysis failed: {e}")
        
        return issues
    
    def _apply_learning_refinement(self, issues: List[CodeIssue], developer_id: str) -> List[CodeIssue]:
        """Apply learning-based refinement to issues"""
        refined_issues = []
        
        for issue in issues:
            # Get historical feedback for similar issues
            feedback_score = self._get_feedback_score(issue, developer_id)
            
            # Adjust confidence based on learning
            issue.confidence *= feedback_score
            
            # Skip issues with very low confidence after learning
            if issue.confidence < self.config["ml_analysis"]["confidence_threshold"]:
                continue
            
            # Enhance explanation based on learning
            issue.explanation = self._enhance_explanation_with_learning(issue, developer_id)
            
            refined_issues.append(issue)
        
        return refined_issues
    
    def _intelligent_prioritization(self, issues: List[CodeIssue], developer_id: str, project_context: Optional[ProjectContext]) -> List[CodeIssue]:
        """Intelligent prioritization based on multiple factors"""
        for issue in issues:
            priority_score = 0.0
            
            # Base score from severity and confidence
            severity_weights = {"critical": 1.0, "major": 0.8, "minor": 0.5, "suggestion": 0.3}
            priority_score += severity_weights.get(issue.severity, 0.3) * issue.confidence
            
            # Adjust for developer experience
            developer_profile = self._get_developer_profile(developer_id)
            exp_multiplier = self._get_experience_multiplier(issue, developer_profile)
            priority_score *= exp_multiplier
            
            # Adjust for project context
            if project_context:
                context_multiplier = self._get_context_multiplier(issue, project_context)
                priority_score *= context_multiplier
            
            # Add urgency factor
            urgency_factor = self._calculate_urgency_factor(issue)
            priority_score += urgency_factor
            
            issue.priority_score = priority_score
        
        # Sort by priority score
        return sorted(issues, key=lambda x: x.priority_score, reverse=True)
    
    def learn_from_feedback(self, issue_id: str, developer_id: str, action: str, feedback: str = "", fix_applied: str = None):
        """Enhanced learning from developer feedback"""
        print(f"📚 Learning from feedback: {action} for issue {issue_id}")
        
        # Store in database
        conn = sqlite3.connect(self.learning_system["feedback_db"])
        conn.execute('''
            INSERT INTO feedback (issue_id, developer_id, action, feedback, timestamp, issue_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (issue_id, developer_id, action, feedback, datetime.now().isoformat(), "unknown", 0.0))
        conn.commit()
        conn.close()
        
        # Update learning patterns
        self._update_learning_patterns(issue_id, developer_id, action, feedback)
        
        # Save learning data
        self._save_learning_data()
        
        print(f"✅ Learning updated for developer {developer_id}")
    
    def generate_intelligent_report(self, issues: List[CodeIssue], output_path: str = "intelligent_lint_report.html") -> str:
        """Generate an intelligent, interactive HTML report"""
        html_content = self._generate_advanced_html_report(issues)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"📊 Intelligent report generated: {output_path}")
        return output_path
    
    def analyze_project_intelligent(self, project_path: str, developer_id: str = "default") -> Dict[str, Any]:
        """Intelligent project-wide analysis with Mistral AI suggestions"""
        print(f"🧠 Starting intelligent project analysis: {project_path}")
        # Build project context
        project_context = self._build_project_context(project_path)
        all_issues = []
        file_count = 0
        analysis_stats = {
            "total_files": 0,
            "analyzed_files": 0,
            "skipped_files": 0,
            "total_issues": 0,
            "critical_issues": 0,
            "major_issues": 0,
            "minor_issues": 0,
            "suggestions": 0,
            "ml_detected": 0,
            "auto_fixable": 0
        }
        # Find and analyze Python files
        python_files = list(Path(project_path).rglob("*.py"))
        analysis_stats["total_files"] = len(python_files)
        for file_path in python_files:
            if self._should_skip_file(str(file_path)):
                analysis_stats["skipped_files"] += 1
                continue
            try:
                print(f"  📄 Analyzing: {file_path.name}")
                file_issues = self.analyze_file_intelligent(str(file_path), developer_id, project_context)
                all_issues.extend(file_issues)
                analysis_stats["analyzed_files"] += 1
                for issue in file_issues:
                    analysis_stats[f"{issue.severity}_issues"] += 1
                    if "ml-detected" in issue.learning_tags:
                        analysis_stats["ml_detected"] += 1
                    if issue.auto_fixable:
                        analysis_stats["auto_fixable"] += 1
            except Exception as e:
                print(f"  ⚠️ Failed to analyze {file_path}: {e}")
                analysis_stats["skipped_files"] += 1
        analysis_stats["total_issues"] = len(all_issues)
        # --- Mistral AI Integration ---
        if all_issues:
            mistral_suggestions = self._get_mistral_suggestions(all_issues)
            for issue, suggestion in zip(all_issues, mistral_suggestions):
                issue.suggestion = suggestion  # Attach Mistral suggestion to each issue
        # Generate comprehensive report
        report_path = self.generate_intelligent_report(all_issues, f"{project_path}/intelligent_lint_report.html")
        insights = self._generate_project_insights(all_issues, analysis_stats, project_context)
        return {
            "issues": all_issues,
            "stats": analysis_stats,
            "insights": insights,
            "report_path": report_path,
            "project_context": project_context
        }

    def _get_mistral_suggestions(self, issues):
        """Send issues to Mistral AI API and return suggestions."""
        if not issues:
            return []
        
        # Get API key from environment
        api_key = os.getenv('MISTRAL_API_KEY')
        if not api_key:
            print("Mistral API key not found in environment variables")
            return ["No suggestion available"] * len(issues)
        
        # Prepare payload for Mistral API
        issue_descriptions = []
        for issue in issues:
            issue_desc = f"File: {issue.file_path}, Line: {issue.line_number}, Type: {issue.issue_type}, Severity: {issue.severity}, Title: {issue.title}"
            issue_descriptions.append(issue_desc)
        
        prompt = (
            "The following code issues were found. For each issue, provide a clear, actionable suggestion to fix it. "
            "Make the suggestions human-friendly and specific.\n\n"
        )
        prompt += "\n\n".join(f"Issue {i+1}: {desc}" for i, desc in enumerate(issue_descriptions))
        
        # Use the correct Mistral API endpoint
        api_url = "https://api.mistral.ai/v1/chat/completions"
        
        # Prepare the request payload
        payload = {
            "model": "mistral-small",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                api_url, 
                json=payload, 
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('choices') and len(result['choices']) > 0:
                    suggestions_text = result['choices'][0]['message']['content']
                    # Split the response into individual suggestions
                    # This is a simple approach - in production you might want more sophisticated parsing
                    suggestions = suggestions_text.split('\n\n')
                    # Ensure we have the right number of suggestions
                    while len(suggestions) < len(issues):
                        suggestions.append("No suggestion available")
                    return suggestions[:len(issues)]
                else:
                    print("No content in Mistral API response")
                    return ["No suggestion available"] * len(issues)
            else:
                print(f"Mistral API error: {response.status_code} {response.text}")
                return ["No suggestion available"] * len(issues)
        except Exception as e:
            print(f"Mistral API call failed: {e}")
            return ["No suggestion available"] * len(issues)
    
    # ================================
    # HELPER METHODS
    # ================================
    
    def _smart_chunk_code(self, code: str, max_chunk_size: int = 800) -> List[str]:
        """Intelligently chunk code for analysis"""
        lines = code.split('\\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\\n'.join(current_chunk))
        
        return chunks
    
    def _parse_ml_review_output(self, file_path: str, code: str, analysis: str, chunk_idx: int) -> List[CodeIssue]:
        """Parse ML review output into structured issues (minimal, no suggestions/explanations)"""
        issues = []
        # Simple parsing - in production, this would be more sophisticated
        issue_indicators = [
            "issue", "problem", "bug", "error", "warning", 
            "vulnerability", "improvement", "optimize", "refactor"
        ]
        if any(indicator in analysis.lower() for indicator in issue_indicators):
            # Determine severity based on keywords
            severity = "suggestion"
            if any(word in analysis.lower() for word in ["critical", "severe", "dangerous"]):
                severity = "critical"
            elif any(word in analysis.lower() for word in ["major", "important", "significant"]):
                severity = "major"
            elif any(word in analysis.lower() for word in ["minor", "small", "trivial"]):
                severity = "minor"
            # Only include minimal info for each issue
            issue = CodeIssue(
                id=self._generate_issue_id(file_path, chunk_idx, "ml_review"),
                file_path=file_path,
                line_number=chunk_idx + 1,
                column=0,
                issue_type="ml_review",
                severity=severity,
                title="ML Code Review Finding",
                description="",
                explanation="",
                suggested_fix="",
                confidence=0.0,
                ml_reasoning="",
                code_snippet="",
                context=f"Chunk {chunk_idx}",
                related_files=[],
                learning_tags=["ml-review", "code-quality"],
                fix_examples=[],
                references=[],
                timestamp=datetime.now().isoformat(),
                priority_score=0.0,
                developer_notes="",
                auto_fixable=False
            )
            issues.append(issue)
        return issues
    
    def _generate_issue_id(self, file_path: str, line_num: int, issue_type: str) -> str:
        """Generate unique issue ID"""
        content = f"{file_path}:{line_num}:{issue_type}:{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _should_skip_file(self, file_path: str) -> bool:
        """Determine if file should be skipped"""
        skip_patterns = [
            "__pycache__", ".git", ".venv", "venv", "env",
            "node_modules", ".pytest_cache", "build", "dist"
        ]
        return any(pattern in file_path for pattern in skip_patterns)
    
    def _build_project_context(self, project_path: str) -> ProjectContext:
        """Build comprehensive project context"""
        # This would analyze the project structure, dependencies, etc.
        return ProjectContext(
            project_path=project_path,
            project_type="general",
            dependencies=[],
            coding_standards={},
            security_requirements=[],
            performance_targets={},
            file_relationships={},
            common_patterns=[]
        )
    
    def _get_developer_profile(self, developer_id: str) -> DeveloperProfile:
        """Get or create developer profile"""
        # This would load from database or create default
        return DeveloperProfile(
            id=developer_id,
            name=developer_id,
            experience_level="intermediate",
            preferred_style={},
            learning_goals=[],
            feedback_history=[],
            skill_areas=[],
            project_roles=[],
            last_active=datetime.now().isoformat()
        )
    
    # Additional helper methods would be implemented...
    def _update_file_context(self, file_path: str, code: str): pass
    def _analyze_imports_intelligent(self, file_path: str, code: str, project_context): return []
    def _analyze_function_relationships(self, file_path: str, code: str): return []
    def _analyze_project_consistency(self, file_path: str, code: str, project_context): return []
    def _find_security_pattern_issues(self, file_path: str, code: str, pattern_info): return []
    def _find_performance_pattern_issues(self, file_path: str, code: str, pattern_info): return []
    def _parse_security_analysis(self, file_path: str, code: str, analysis): return []
    def _parse_performance_analysis(self, file_path: str, code: str, analysis): return []
    def _get_feedback_score(self, issue: CodeIssue, developer_id: str): return 1.0
    def _enhance_explanation_with_learning(self, issue: CodeIssue, developer_id: str): return issue.explanation
    def _get_experience_multiplier(self, issue: CodeIssue, profile: DeveloperProfile): return 1.0
    def _get_context_multiplier(self, issue: CodeIssue, context: ProjectContext): return 1.0
    def _calculate_urgency_factor(self, issue: CodeIssue): return 0.0
    def _update_learning_patterns(self, issue_id: str, developer_id: str, action: str, feedback: str): pass
    def _save_learning_data(self): pass
    def _generate_advanced_html_report(self, issues: List[CodeIssue]): return "<html><body><h1>Advanced ML Lint Report</h1></body></html>"
    def _generate_project_insights(self, issues: List[CodeIssue], stats: Dict, context: ProjectContext): return {}
    def _generate_architectural_fix(self, analysis: str): return "Consider refactoring the architecture"
    def _extract_fix_from_analysis(self, analysis: str): return "Apply suggested improvements"
    def _is_auto_fixable(self, analysis: str): return False

    def get_no_issues_explanation(self, checked_files: list) -> str:
        """Call Mistral API to explain why checked files are correct and have no lint issues."""
        if not checked_files:
            return "No files were checked."
        
        # Get API key from environment
        api_key = os.getenv('MISTRAL_API_KEY')
        if not api_key:
            print("Mistral API key not found in environment variables")
            return "No issues explanation available - API key not configured."
        
        # Compose prompt
        prompt = (
            "No lint issues were found in the following Python files. "
            "For each file, provide a short, 2-line explanation in markdown: "
            "use a main bullet for the file name, and two sub-bullets—one for the file's purpose, one for why there are no issues. "
            "Keep each explanation concise and human-friendly. Example format:\n\n"
            "• app.py\n   - Main application file.\n   - No lint issues: code follows best practices.\n\n"
            "• test_app.py\n   - Contains tests.\n   - No lint issues: test code is clean.\n\n"
            "Now, generate explanations for all the other files which are analyzed by the agent:\n\n"
        )
        prompt += "\n".join(f"• {os.path.basename(f)}" for f in checked_files)
        
        # Use the correct Mistral API endpoint
        api_url = "https://api.mistral.ai/v1/chat/completions"
        
        # Prepare the request payload
        payload = {
            "model": "mistral-small",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                api_url, 
                json=payload, 
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('choices') and len(result['choices']) > 0:
                    explanation = result['choices'][0]['message']['content']
                    return explanation
                else:
                    print("No content in Mistral API response")
                    return "No issues explanation available."
            else:
                print(f"Mistral API error: {response.status_code} {response.text}")
                return "No issues explanation available."
        except Exception as e:
            print(f"Mistral API call failed: {e}")
            return "No issues explanation available."

# ================================
# CLI INTERFACE
# ================================

def main():
    """Enhanced CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Advanced ML-Integrated Lint Agent")
    parser.add_argument("path", help="File or directory to analyze")
    parser.add_argument("--developer-id", default="default", help="Developer ID for personalization")
    parser.add_argument("--output", default="intelligent_lint_report.html", help="Output report file")
    parser.add_argument("--config", default="./advanced_ml_lint_config.json", help="Config file path")
    parser.add_argument("--mode", choices=["file", "project", "interactive"], default="auto", help="Analysis mode")
    parser.add_argument("--learning", action="store_true", help="Enable learning mode")
    
    args = parser.parse_args()
    
    # Initialize advanced agent
    print("🚀 Starting Advanced ML Lint Agent...")
    agent = AdvancedMLLintAgent(config_path=args.config)
    
    try:
        if os.path.isfile(args.path):
            print(f"\\n📄 Analyzing file: {args.path}")
            issues = agent.analyze_file_intelligent(args.path, args.developer_id)
            
            print(f"\\n🎯 Analysis Results: {len(issues)} issues found")
            for i, issue in enumerate(issues[:3], 1):
                print(f"\\n{i}. 🔍 {issue.title}")
                print(f"   📍 {issue.file_path}:{issue.line_number}")
                print(f"   ⚠️  {issue.severity.upper()}")
                print(f"   📝 {issue.description}")
                print(f"   💡 {issue.suggested_fix}")
                print(f"   🎯 Confidence: {issue.confidence:.1%}")
                print(f"   🧠 ML Reasoning: {issue.ml_reasoning[:100]}...")
        
        elif os.path.isdir(args.path):
            print(f"\\n📁 Analyzing project: {args.path}")
            result = agent.analyze_project_intelligent(args.path, args.developer_id)
            
            print(f"\\n🎯 Project Analysis Complete!")
            print(f"   📊 Files analyzed: {result['stats']['analyzed_files']}")
            print(f"   🚨 Total issues: {result['stats']['total_issues']}")
            print(f"   🔴 Critical: {result['stats']['critical_issues']}")
            print(f"   🟡 Major: {result['stats']['major_issues']}")
            print(f"   🟢 Minor: {result['stats']['minor_issues']}")
            print(f"   💡 Suggestions: {result['stats']['suggestions']}")
            print(f"   🤖 ML Detected: {result['stats']['ml_detected']}")
            print(f"   🔧 Auto-fixable: {result['stats']['auto_fixable']}")
            print(f"   📊 Report: {result['report_path']}")
        
        else:
            print(f"❌ Path not found: {args.path}")
    
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
