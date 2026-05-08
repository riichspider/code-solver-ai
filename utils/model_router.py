"""Intelligent model routing for optimal LLM selection.

Analyzes problem characteristics and automatically selects the best model
based on complexity, language, and sensitivity requirements.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger


class ModelCategory(Enum):
    """Model categories for routing decisions."""
    SIMPLE_QUERY = "simple_query"
    COMPLEX_ALGORITHM = "complex_algorithm"
    SECURITY_SENSITIVE = "security_sensitive"
    MULTILINGUAL = "multilingual"
    PERFORMANCE_CRITICAL = "performance_critical"
    DATA_HEAVY = "data_heavy"


@dataclass
class ProblemAnalysis:
    """Analysis result for a coding problem."""
    complexity_score: float  # 0.0 to 1.0
    language: str
    has_sensitive_data: bool
    estimated_tokens: int
    problem_type: str
    keywords: List[str]
    file_operations: bool
    network_operations: bool
    database_operations: bool
    multilingual_components: int


@dataclass
class ModelRecommendation:
    """Model recommendation with reasoning."""
    model: str
    category: ModelCategory
    confidence: float
    reasoning: List[str]
    fallback_models: List[str]


class IntelligentModelRouter:
    """Intelligent routing system for model selection."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = get_logger("model_router")
        self.config = config or {}
        
        # Model configurations with capabilities
        self.model_capabilities = {
            "qwen2.5-coder:latest": {
                "strengths": ["code_generation", "speed", "cost_efficiency"],
                "max_tokens": 32768,
                "cost_per_token": 0.0001,
                "speed": "fast",
                "complexity_limit": 0.7,
                "languages": ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "ruby", "php"]
            },
            "llama-3.3-70b-versatile": {
                "strengths": ["reasoning", "complex_algorithms", "multilingual"],
                "max_tokens": 131072,
                "cost_per_token": 0.0005,
                "speed": "medium",
                "complexity_limit": 0.9,
                "languages": ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "ruby", "php", "c", "csharp"]
            },
            "gemini-2.0-flash": {
                "strengths": ["security", "safety", "multimodal", "reasoning"],
                "max_tokens": 8192,
                "cost_per_token": 0.0003,
                "speed": "fast",
                "complexity_limit": 0.85,
                "languages": ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "ruby", "php", "swift", "kotlin"]
            }
        }
        
        # Complexity indicators
        self.complexity_patterns = {
            "algorithms": [
                r'\b(sort|search|graph|tree|heap|stack|queue|linked.?list|binary.?tree|avl|red.?black)\b',
                r'\b(dynamic.?programming|dp|greedy|divide.?and.?conquer|backtracking)\b',
                r'\b(recursion|memoization|cache|optimization)\b',
                r'\b(time.?complexity|space.?complexity|big.?o|o\(.*?\))\b'
            ],
            "data_structures": [
                r'\b(array|list|vector|matrix|hash.?table|dictionary|map|set)\b',
                r'\b(class|struct|interface|abstract|inheritance|polymorphism)\b'
            ],
            "concurrency": [
                r'\b(thread|async|await|coroutine|goroutine|future|promise)\b',
                r'\b(mutex|semaphore|lock|concurrent|parallel)\b',
                r'\b(race.?condition|deadlock|synchronization)\b'
            ],
            "security": [
                r'\b(authentication|authorization|password|token|jwt|oauth)\b',
                r'\b(encrypt|decrypt|hash|salt|cipher|ssl|tls)\b',
                r'\b(sql.?injection|xss|csrf|security|vulnerability)\b',
                r'\b(private.?key|public.?key|certificate|ssl|https)\b'
            ],
            "performance": [
                r'\b(performance|optimization|benchmark|profiling)\b',
                r'\b(memory.?leak|garbage.?collection|heap|stack)\b',
                r'\b(caching|lazy.?loading|eager.?loading)\b'
            ],
            "file_operations": [
                r'\b(file|directory|path|read|write|append|delete|copy)\b',
                r'\b(json|xml|csv|yaml|config|ini)\b'
            ],
            "network": [
                r'\b(http|https|api|rest|graphql|websocket|tcp|udp)\b',
                r'\b(request|response|client|server|endpoint)\b'
            ],
            "database": [
                r'\b(sql|database|query|select|insert|update|delete)\b',
                r'\b(table|schema|index|foreign.?key|join)\b'
            ]
        }
        
        # Compile regex patterns for efficiency
        self.compiled_patterns = {
            category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for category, patterns in self.complexity_patterns.items()
        }
        
        # Language-specific complexity indicators
        self.language_complexity = {
            "python": {
                "simple_keywords": ["print", "input", "len", "range", "list", "dict"],
                "complex_keywords": ["decorator", "metaclass", "generator", "comprehension", "asyncio", "multiprocessing"],
                "base_complexity": 0.3
            },
            "javascript": {
                "simple_keywords": ["console.log", "alert", "prompt", "document", "window"],
                "complex_keywords": ["closure", "prototype", "promise", "async/await", "callback", "hoisting"],
                "base_complexity": 0.4
            },
            "java": {
                "simple_keywords": ["System.out", "Scanner", "String", "int", "double"],
                "complex_keywords": ["reflection", "annotation", "generic", "lambda", "stream", "concurrent"],
                "base_complexity": 0.5
            },
            "go": {
                "simple_keywords": ["fmt", "os", "strings", "strconv"],
                "complex_keywords": ["goroutine", "channel", "select", "interface", "defer"],
                "base_complexity": 0.4
            },
            "rust": {
                "simple_keywords": ["println!", "vec!", "String", "i32", "f64"],
                "complex_keywords": ["lifetime", "borrow", "trait", "macro", "unsafe", "async"],
                "base_complexity": 0.6
            }
        }
    
    def analyze_problem(self, problem_text: str, language: str = "python") -> ProblemAnalysis:
        """Analyze a coding problem to determine characteristics."""
        problem_lower = problem_text.lower()
        
        # Extract keywords
        keywords = self._extract_keywords(problem_text)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(problem_text, language)
        
        # Check for sensitive data
        has_sensitive_data = self._detect_sensitive_data(problem_text)
        
        # Estimate token count
        estimated_tokens = self._estimate_tokens(problem_text)
        
        # Determine problem type
        problem_type = self._classify_problem_type(problem_text, keywords)
        
        # Check for specific operations
        file_operations = self._has_pattern_match(problem_text, "file_operations")
        network_operations = self._has_pattern_match(problem_text, "network")
        database_operations = self._has_pattern_match(problem_text, "database")
        
        # Count multilingual components
        multilingual_components = self._count_multilingual_components(problem_text)
        
        return ProblemAnalysis(
            complexity_score=complexity_score,
            language=language,
            has_sensitive_data=has_sensitive_data,
            estimated_tokens=estimated_tokens,
            problem_type=problem_type,
            keywords=keywords,
            file_operations=file_operations,
            network_operations=network_operations,
            database_operations=database_operations,
            multilingual_components=multilingual_components
        )
    
    def select_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Select the best model based on problem analysis."""
        
        # Priority 1: Security-sensitive problems
        if analysis.has_sensitive_data:
            return self._recommend_security_model(analysis, available_models)
        
        # Priority 2: High complexity problems
        if analysis.complexity_score > 0.8:
            return self._recommend_complex_model(analysis, available_models)
        
        # Priority 3: Multilingual problems
        if analysis.multilingual_components > 1:
            return self._recommend_multilingual_model(analysis, available_models)
        
        # Priority 4: Performance-critical problems
        if self._is_performance_critical(analysis):
            return self._recommend_performance_model(analysis, available_models)
        
        # Default: Simple query
        return self._recommend_simple_model(analysis, available_models)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from problem text."""
        # Simple keyword extraction - can be enhanced with NLP
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must'}
        
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Return unique keywords, sorted by frequency
        from collections import Counter
        word_counts = Counter(keywords)
        return [word for word, _ in word_counts.most_common(20)]
    
    def _calculate_complexity_score(self, text: str, language: str) -> float:
        """Calculate complexity score from 0.0 to 1.0."""
        base_score = self.language_complexity.get(language, {}).get("base_complexity", 0.4)
        
        # Add complexity based on patterns
        pattern_scores = {
            "algorithms": 0.3,
            "data_structures": 0.2,
            "concurrency": 0.4,
            "security": 0.3,
            "performance": 0.2,
            "file_operations": 0.1,
            "network": 0.2,
            "database": 0.2
        }
        
        total_score = base_score
        
        for category, patterns in self.compiled_patterns.items():
            category_score = 0
            for pattern in patterns:
                matches = pattern.findall(text)
                category_score += len(matches) * 0.1
            
            total_score += min(category_score, pattern_scores.get(category, 0.1))
        
        # Consider text length (longer problems tend to be more complex)
        length_factor = min(len(text) / 2000, 0.2)
        total_score += length_factor
        
        return min(total_score, 1.0)
    
    def _detect_sensitive_data(self, text: str) -> bool:
        """Detect if problem involves sensitive data or security."""
        sensitive_patterns = [
            r'\b(password|passwd|pwd|secret|key|token|api.?key|credential)\b',
            r'\b(authentication|authorization|login|signin|signup)\b',
            r'\b(encrypt|decrypt|hash|salt|cipher|ssl|tls|https)\b',
            r'\b(private.?key|public.?key|certificate|ssl|jwt|oauth)\b',
            r'\b(sql.?injection|xss|csrf|security|vulnerability)\b',
            r'\b(personal|pii|ssn|credit.?card|financial|bank)\b'
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for the problem."""
        return len(text) // 4  # Rough approximation
    
    def _classify_problem_type(self, text: str, keywords: List[str]) -> str:
        """Classify the type of problem."""
        if any(kw in keywords for kw in ['algorithm', 'sort', 'search', 'optimize']):
            return "algorithm"
        elif any(kw in keywords for kw in ['bug', 'error', 'fix', 'debug']):
            return "debugging"
        elif any(kw in keywords for kw in ['implement', 'create', 'build', 'write']):
            return "implementation"
        elif any(kw in keywords for kw in ['test', 'unit', 'spec', 'verify']):
            return "testing"
        elif any(kw in keywords for kw in ['refactor', 'improve', 'optimize']):
            return "refactoring"
        else:
            return "general"
    
    def _has_pattern_match(self, text: str, category: str) -> bool:
        """Check if text matches patterns in a category."""
        patterns = self.compiled_patterns.get(category, [])
        return any(pattern.search(text) for pattern in patterns)
    
    def _count_multilingual_components(self, text: str) -> int:
        """Count components that suggest multilingual requirements."""
        multilingual_indicators = [
            r'\b(api|rest|graphql|websocket)\b',
            r'\b(json|xml|yaml|csv)\b',
            r'\b(integration|interface|protocol)\b',
            r'\b(frontend|backend|full.?stack)\b'
        ]
        
        count = 0
        for pattern in multilingual_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                count += 1
        
        return count
    
    def _is_performance_critical(self, analysis: ProblemAnalysis) -> bool:
        """Determine if problem is performance-critical."""
        performance_indicators = [
            "performance", "optimization", "speed", "fast", "slow",
            "memory", "cpu", "benchmark", "efficiency"
        ]
        
        return any(indicator in analysis.keywords for indicator in performance_indicators)
    
    def _recommend_security_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Recommend model for security-sensitive problems."""
        preferred = "gemini-2.0-flash"
        
        if preferred in available_models:
            return ModelRecommendation(
                model=preferred,
                category=ModelCategory.SECURITY_SENSITIVE,
                confidence=0.9,
                reasoning=[
                    "Security-sensitive problem detected",
                    "Gemini has strong safety and security capabilities",
                    "Better handling of authentication/authorization patterns"
                ],
                fallback_models=["llama-3.3-70b-versatile", "qwen2.5-coder:latest"]
            )
        
        # Fallback to next best
        for model in ["llama-3.3-70b-versatile", "qwen2.5-coder:latest"]:
            if model in available_models:
                return ModelRecommendation(
                    model=model,
                    category=ModelCategory.SECURITY_SENSITIVE,
                    confidence=0.7,
                    reasoning=["Security problem, using available model"],
                    fallback_models=[m for m in available_models if m != model]
                )
        
        # Last resort
        return ModelRecommendation(
            model=available_models[0],
            category=ModelCategory.SECURITY_SENSITIVE,
            confidence=0.5,
            reasoning=["Limited options for security problem"],
            fallback_models=available_models[1:]
        )
    
    def _recommend_complex_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Recommend model for complex problems."""
        preferred = "llama-3.3-70b-versatile"
        
        if preferred in available_models:
            return ModelRecommendation(
                model=preferred,
                category=ModelCategory.COMPLEX_ALGORITHM,
                confidence=0.85,
                reasoning=[
                    f"High complexity score ({analysis.complexity_score:.2f}) detected",
                    "Llama 3.3 70B excels at complex reasoning",
                    "Better handling of algorithms and data structures"
                ],
                fallback_models=["gemini-2.0-flash", "qwen2.5-coder:latest"]
            )
        
        # Try Gemini next
        if "gemini-2.0-flash" in available_models:
            return ModelRecommendation(
                model="gemini-2.0-flash",
                category=ModelCategory.COMPLEX_ALGORITHM,
                confidence=0.8,
                reasoning=["Complex problem, using Gemini"],
                fallback_models=[m for m in available_models if m != "gemini-2.0-flash"]
            )
        
        # Fallback
        return ModelRecommendation(
            model=available_models[0],
            category=ModelCategory.COMPLEX_ALGORITHM,
            confidence=0.6,
            reasoning=["Complex problem with limited model options"],
            fallback_models=available_models[1:]
        )
    
    def _recommend_multilingual_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Recommend model for multilingual problems."""
        preferred = "llama-3.3-70b-versatile"
        
        if preferred in available_models:
            return ModelRecommendation(
                model=preferred,
                category=ModelCategory.MULTILINGUAL,
                confidence=0.8,
                reasoning=[
                    f"Multilingual components detected ({analysis.multilingual_components})",
                    "Llama 3.3 has strong multilingual capabilities",
                    "Better for API integration and cross-language patterns"
                ],
                fallback_models=["gemini-2.0-flash", "qwen2.5-coder:latest"]
            )
        
        # Try Gemini next
        if "gemini-2.0-flash" in available_models:
            return ModelRecommendation(
                model="gemini-2.0-flash",
                category=ModelCategory.MULTILINGUAL,
                confidence=0.75,
                reasoning=["Multilingual problem, using Gemini"],
                fallback_models=[m for m in available_models if m != "gemini-2.0-flash"]
            )
        
        # Fallback
        return ModelRecommendation(
            model=available_models[0],
            category=ModelCategory.MULTILINGUAL,
            confidence=0.6,
            reasoning=["Multilingual problem with limited options"],
            fallback_models=available_models[1:]
        )
    
    def _recommend_performance_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Recommend model for performance-critical problems."""
        # For performance problems, prefer faster models
        preferred = "qwen2.5-coder:latest"
        
        if preferred in available_models:
            return ModelRecommendation(
                model=preferred,
                category=ModelCategory.PERFORMANCE_CRITICAL,
                confidence=0.8,
                reasoning=[
                    "Performance-critical problem detected",
                    "Qwen2.5 offers fast response times",
                    "Good for optimization and profiling tasks"
                ],
                fallback_models=["gemini-2.0-flash", "llama-3.3-70b-versatile"]
            )
        
        # Try Gemini for speed
        if "gemini-2.0-flash" in available_models:
            return ModelRecommendation(
                model="gemini-2.0-flash",
                category=ModelCategory.PERFORMANCE_CRITICAL,
                confidence=0.75,
                reasoning=["Performance problem, using Gemini for speed"],
                fallback_models=[m for m in available_models if m != "gemini-2.0-flash"]
            )
        
        # Fallback
        return ModelRecommendation(
            model=available_models[0],
            category=ModelCategory.PERFORMANCE_CRITICAL,
            confidence=0.6,
            reasoning=["Performance problem with limited options"],
            fallback_models=available_models[1:]
        )
    
    def _recommend_simple_model(self, analysis: ProblemAnalysis, available_models: List[str]) -> ModelRecommendation:
        """Recommend model for simple problems."""
        # For simple problems, prefer cost-effective fast models
        preferred = "qwen2.5-coder:latest"
        
        if preferred in available_models:
            return ModelRecommendation(
                model=preferred,
                category=ModelCategory.SIMPLE_QUERY,
                confidence=0.9,
                reasoning=[
                    f"Simple problem detected (complexity: {analysis.complexity_score:.2f})",
                    "Qwen2.5 is cost-effective for simple queries",
                    "Fast response times for straightforward tasks"
                ],
                fallback_models=["gemini-2.0-flash", "llama-3.3-70b-versatile"]
            )
        
        # Try Gemini next
        if "gemini-2.0-flash" in available_models:
            return ModelRecommendation(
                model="gemini-2.0-flash",
                category=ModelCategory.SIMPLE_QUERY,
                confidence=0.8,
                reasoning=["Simple problem, using Gemini"],
                fallback_models=[m for m in available_models if m != "gemini-2.0-flash"]
            )
        
        # Fallback
        return ModelRecommendation(
            model=available_models[0],
            category=ModelCategory.SIMPLE_QUERY,
            confidence=0.7,
            reasoning=["Simple problem with limited options"],
            fallback_models=available_models[1:]
        )
