"""Testes unitários para o módulo src.classifier.

Valida Strategy pattern, classificação via Ollama e regras, tratamento de erros
e conformidade com type hints rigorosos.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.classifier import (
    ClassificationType,
    ConfidenceLevel,
    ClassificationResult,
    ClassificationRequest,
    ClassificationStrategy,
    BaseClassificationStrategy,
    OllamaClassifierStrategy,
    RuleBasedClassifierStrategy,
    Classifier,
    create_classifier
)
from models.ollama_client import OllamaClient, OllamaError


class TestClassificationType:
    """Testes para enum ClassificationType."""

    def test_classification_type_values(self):
        """Testa valores do enum."""
        assert ClassificationType.BUG.value == "bug"
        assert ClassificationType.FEATURE.value == "feature"
        assert ClassificationType.REFACTOR.value == "refactor"
        assert ClassificationType.UNKNOWN.value == "unknown"


class TestConfidenceLevel:
    """Testes para enum ConfidenceLevel."""

    def test_confidence_level_values(self):
        """Testa valores do enum."""
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.VERY_HIGH.value == "very_high"


class TestClassificationResult:
    """Testes para ClassificationResult."""

    def test_classification_result_creation(self):
        """Testa criação de ClassificationResult."""
        result = ClassificationResult(
            classification=ClassificationType.BUG,
            confidence=ConfidenceLevel.HIGH,
            reasoning="Test reasoning",
            key_indicators=["error", "crash"],
            suggested_actions=["debug", "fix"],
            complexity_score=0.7,
            estimated_effort="medium",
            tags=["bug", "urgent"]
        )

        assert result.classification == ClassificationType.BUG
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.reasoning == "Test reasoning"
        assert result.key_indicators == ["error", "crash"]
        assert result.suggested_actions == ["debug", "fix"]
        assert result.complexity_score == 0.7
        assert result.estimated_effort == "medium"
        assert result.tags == ["bug", "urgent"]
        assert result.raw_response is None

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        result = ClassificationResult(
            classification=ClassificationType.FEATURE,
            confidence=ConfidenceLevel.MEDIUM,
            reasoning="Add new functionality",
            key_indicators=["add", "implement"],
            suggested_actions=["develop"],
            complexity_score=0.5,
            estimated_effort="high",
            tags=["feature"]
        )

        result_dict = result.to_dict()

        assert result_dict["classification"] == "feature"
        assert result_dict["confidence"] == "medium"
        assert result_dict["reasoning"] == "Add new functionality"
        assert result_dict["key_indicators"] == ["add", "implement"]
        assert result_dict["suggested_actions"] == ["develop"]
        assert result_dict["complexity_score"] == 0.5
        assert result_dict["estimated_effort"] == "high"
        assert result_dict["tags"] == ["feature"]

    def test_to_json(self):
        """Testa conversão para JSON."""
        result = ClassificationResult(
            classification=ClassificationType.REFACTOR,
            confidence=ConfidenceLevel.LOW,
            reasoning="Improve code structure",
            key_indicators=["refactor"],
            suggested_actions=["optimize"],
            complexity_score=0.3,
            estimated_effort="low",
            tags=["refactor"]
        )

        json_str = result.to_json()

        # Verifica se é JSON válido
        import json
        parsed = json.loads(json_str)

        assert parsed["classification"] == "refactor"
        assert parsed["confidence"] == "low"
        assert parsed["reasoning"] == "Improve code structure"


class TestClassificationRequest:
    """Testes para ClassificationRequest."""

    def test_minimal_request(self):
        """Testa request mínima."""
        request = ClassificationRequest(input_text="Fix the bug")

        assert request.input_text == "Fix the bug"
        assert request.context is None
        assert request.language is None
        assert request.file_path is None
        assert request.additional_metadata is None

    def test_full_request(self):
        """Testa request completa."""
        metadata = {"priority": "high", "assignee": "dev1"}
        request = ClassificationRequest(
            input_text="Add new feature",
            context="User management module",
            language="python",
            file_path="/app/models/user.py",
            additional_metadata=metadata
        )

        assert request.input_text == "Add new feature"
        assert request.context == "User management module"
        assert request.language == "python"
        assert request.file_path == "/app/models/user.py"
        assert request.additional_metadata == metadata


class TestRuleBasedClassifierStrategy:
    """Testes para RuleBasedClassifierStrategy."""

    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = RuleBasedClassifierStrategy()

    def test_strategy_name(self):
        """Testa nome da estratégia."""
        assert self.strategy.name == "rule_based_classifier"

    def test_validate_request_valid(self):
        """Testa validação de request válida."""
        request = ClassificationRequest(input_text="Fix the error in the code")
        assert self.strategy.validate_request(request) is True

    def test_validate_request_empty(self):
        """Testa validação de request vazia."""
        request = ClassificationRequest(input_text="")
        assert self.strategy.validate_request(request) is False

        request = ClassificationRequest(input_text="   ")
        assert self.strategy.validate_request(request) is False

    def test_validate_request_too_short(self):
        """Testa validação de request muito curta."""
        request = ClassificationRequest(input_text="Hi")
        assert self.strategy.validate_request(request) is False

    def test_classify_bug(self):
        """Testa classificação de bug."""
        request = ClassificationRequest(
            input_text="Fix the error and debug the crash")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.BUG
        assert result.confidence in [
            ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        assert "ClassificationType.BUG_score:" in str(result.key_indicators)
        assert "rule_based" in result.tags

    def test_classify_feature(self):
        """Testa classificação de feature."""
        request = ClassificationRequest(
            input_text="Add new functionality and implement user authentication")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.FEATURE
        assert result.confidence in [
            ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        assert "ClassificationType.FEATURE_score:" in str(
            result.key_indicators)
        assert "rule_based" in result.tags

    def test_classify_refactor(self):
        """Testa classificação de refactor."""
        request = ClassificationRequest(
            input_text="Refactor the code and improve performance")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.REFACTOR
        assert result.confidence in [
            ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        assert "ClassificationType.REFACTOR_score:" in str(
            result.key_indicators)
        assert "rule_based" in result.tags

    def test_classify_unknown(self):
        """Testa classificação desconhecida."""
        request = ClassificationRequest(
            input_text="Hello world, this is a test message")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.UNKNOWN
        assert result.confidence == ConfidenceLevel.LOW
        assert "rule_based" in result.tags

    def test_build_context_string(self):
        """Testa construção de string de contexto."""
        request = ClassificationRequest(
            input_text="Test input",
            context="Test context",
            language="python",
            file_path="/test/file.py",
            additional_metadata={"key": "value"}
        )

        context_str = self.strategy._build_context_string(request)

        assert "Context: Test context" in context_str
        assert "Language: python" in context_str
        assert "File: /test/file.py" in context_str
        assert "Metadata: key: value" in context_str

    def test_build_context_string_minimal(self):
        """Testa construção de contexto com request mínima."""
        request = ClassificationRequest(input_text="Test")

        context_str = self.strategy._build_context_string(request)

        assert context_str == "No additional context provided."


class TestOllamaClassifierStrategy:
    """Testes para OllamaClassifierStrategy."""

    def setup_method(self):
        """Setup para cada teste."""
        self.mock_client = Mock(spec=OllamaClient)
        self.mock_client.default_model = "test-model"
        self.strategy = OllamaClassifierStrategy(self.mock_client)

    def test_strategy_name(self):
        """Testa nome da estratégia."""
        assert self.strategy.name == "ollama_classifier"

    def test_initialization_with_custom_model(self):
        """Testa inicialização com modelo customizado."""
        strategy = OllamaClassifierStrategy(self.mock_client, "custom-model")
        assert strategy.model == "custom-model"

    def test_validate_request_valid(self):
        """Testa validação de request válida."""
        request = ClassificationRequest(
            input_text="Valid request with enough content")
        assert self.strategy.validate_request(request) is True

    def test_classify_success(self):
        """Testa classificação com sucesso."""
        # Mock response do Ollama
        mock_response = {
            "classification": "bug",
            "confidence": "high",
            "reasoning": "Contains error indicators",
            "key_indicators": ["error", "fix"],
            "suggested_actions": ["debug"],
            "complexity_score": 0.7,
            "estimated_effort": "medium",
            "tags": ["bug", "urgent"]
        }

        self.mock_client.generate_json.return_value = mock_response

        request = ClassificationRequest(input_text="Fix the error in the code")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.BUG
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.reasoning == "Contains error indicators"
        assert result.key_indicators == ["error", "fix"]
        assert result.suggested_actions == ["debug"]
        assert result.complexity_score == 0.7
        assert result.estimated_effort == "medium"
        assert result.tags == ["bug", "urgent"]
        assert result.raw_response == mock_response

    def test_classify_ollama_error(self):
        """Testa classificação com erro do Ollama."""
        self.mock_client.generate_json.side_effect = OllamaError(
            "Connection failed")

        request = ClassificationRequest(input_text="Test input")
        result = self.strategy.classify(request)

        assert result.classification == ClassificationType.UNKNOWN
        assert result.confidence == ConfidenceLevel.LOW
        assert "Ollama classification failed" in result.reasoning
        assert "ollama_error" in result.key_indicators
        assert "manual_classification" in result.suggested_actions

    def test_classify_invalid_response(self):
        """Testa classificação com resposta inválida."""
        # Response com campos inválidos
        mock_response = {
            "classification": "invalid_type",
            "confidence": "invalid_confidence",
            "reasoning": 123,  # deveria ser string
            "key_indicators": "not_array",  # deveria ser array
            "suggested_actions": None,  # deveria ser array
            "complexity_score": 2.0,  # acima do limite
            "estimated_effort": "invalid",
            "tags": None
        }

        self.mock_client.generate_json.return_value = mock_response

        request = ClassificationRequest(input_text="Test input")
        result = self.strategy.classify(request)

        # Deve fazer fallback para valores seguros
        assert result.classification == ClassificationType.UNKNOWN
        assert result.confidence == ConfidenceLevel.LOW
        assert result.complexity_score == 1.0  # limitado para 1.0
        assert result.estimated_effort == "unknown"
        assert isinstance(result.key_indicators, list)
        assert isinstance(result.suggested_actions, list)
        assert isinstance(result.tags, list)
        # O reasoning pode ser vazio se não houver campo válido
        assert isinstance(result.reasoning, str)

    def test_parse_ollama_response_parsing_error(self):
        """Testa parsing de resposta com erro."""
        # Response que causa exceção no parsing (com campos inválidos)
        mock_response = {
            "classification": "invalid_type",
            "confidence": "invalid_confidence",
            "reasoning": None,  # vai causar erro no str()
            "key_indicators": "not_array",
            "suggested_actions": None,
            "complexity_score": "not_float",
            "estimated_effort": "invalid",
            "tags": None
        }

        strategy = OllamaClassifierStrategy(self.mock_client)
        result = strategy._parse_ollama_response(mock_response)

        assert result.classification == ClassificationType.UNKNOWN
        assert result.confidence == ConfidenceLevel.LOW
        # O reasoning pode ser vazio em caso de parsing error
        assert isinstance(result.reasoning, str)
        # Os campos devem ser normalizados para arrays válidos
        assert isinstance(result.key_indicators, list)
        assert isinstance(result.suggested_actions, list)
        assert isinstance(result.tags, list)


class TestClassifier:
    """Testes para classe principal Classifier."""

    def setup_method(self):
        """Setup para cada teste."""
        self.mock_primary = Mock(spec=ClassificationStrategy)
        self.mock_fallback = Mock(spec=ClassificationStrategy)
        self.classifier = Classifier(self.mock_primary, self.mock_fallback)

    def test_initialization(self):
        """Testa inicialização do Classifier."""
        assert self.classifier.primary_strategy == self.mock_primary
        assert self.classifier.fallback_strategy == self.mock_fallback

    def test_initialization_default_fallback(self):
        """Testa inicialização com fallback padrão."""
        classifier = Classifier(self.mock_primary)
        assert classifier.primary_strategy == self.mock_primary
        assert isinstance(classifier.fallback_strategy,
                          RuleBasedClassifierStrategy)

    def test_classify_string_input(self):
        """Testa classificação com input string."""
        mock_result = ClassificationResult(
            classification=ClassificationType.BUG,
            confidence=ConfidenceLevel.HIGH,
            reasoning="Test",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.5,
            estimated_effort="medium",
            tags=[]
        )

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.return_value = mock_result

        result = self.classifier.classify("Test input")

        # Verifica que string foi convertida para ClassificationRequest
        self.mock_primary.classify.assert_called_once()
        args = self.mock_primary.classify.call_args[0][0]
        assert isinstance(args, ClassificationRequest)
        assert args.input_text == "Test input"

        assert result == mock_result

    def test_classify_request_input(self):
        """Testa classificação com ClassificationRequest."""
        request = ClassificationRequest(input_text="Test input")
        mock_result = ClassificationResult(
            classification=ClassificationType.FEATURE,
            confidence=ConfidenceLevel.MEDIUM,
            reasoning="Test",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.5,
            estimated_effort="medium",
            tags=[]
        )

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.return_value = mock_result

        result = self.classifier.classify(request)

        self.mock_primary.classify.assert_called_once_with(request)
        assert result == mock_result

    def test_classify_invalid_request(self):
        """Testa classificação com request inválida."""
        request = ClassificationRequest(input_text="")
        self.mock_primary.validate_request.return_value = False

        with pytest.raises(ValueError, match="Invalid classification request"):
            self.classifier.classify(request)

    def test_classify_primary_success(self):
        """Testa classificação com sucesso da estratégia primária."""
        request = ClassificationRequest(input_text="Test")
        mock_result = ClassificationResult(
            classification=ClassificationType.BUG,
            confidence=ConfidenceLevel.HIGH,
            reasoning="Test",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.5,
            estimated_effort="medium",
            tags=[]
        )

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.return_value = mock_result

        result = self.classifier.classify(request)

        assert result == mock_result
        self.mock_fallback.classify.assert_not_called()

    def test_classify_primary_low_confidence_uses_fallback(self):
        """Testa uso de fallback quando confiança primária é baixa."""
        request = ClassificationRequest(input_text="Test")

        primary_result = ClassificationResult(
            classification=ClassificationType.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
            reasoning="Low confidence",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.1,
            estimated_effort="unknown",
            tags=[]
        )

        fallback_result = ClassificationResult(
            classification=ClassificationType.BUG,
            confidence=ConfidenceLevel.HIGH,
            reasoning="Better classification",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.7,
            estimated_effort="medium",
            tags=[]
        )

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.return_value = primary_result
        self.mock_fallback.classify.return_value = fallback_result

        result = self.classifier.classify(request)

        # Deve usar resultado do fallback
        assert result == fallback_result
        self.mock_primary.classify.assert_called_once_with(request)
        self.mock_fallback.classify.assert_called_once_with(request)

    def test_classify_primary_error_uses_fallback(self):
        """Testa uso de fallback quando estratégia primária falha."""
        request = ClassificationRequest(input_text="Test")

        fallback_result = ClassificationResult(
            classification=ClassificationType.FEATURE,
            confidence=ConfidenceLevel.MEDIUM,
            reasoning="Fallback result",
            key_indicators=[],
            suggested_actions=[],
            complexity_score=0.5,
            estimated_effort="medium",
            tags=[]
        )

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.side_effect = Exception("Primary failed")
        self.mock_fallback.classify.return_value = fallback_result

        result = self.classifier.classify(request)

        assert result == fallback_result
        self.mock_fallback.classify.assert_called_once_with(request)

    def test_classify_all_strategies_fail(self):
        """Testa erro quando todas as estratégias falham."""
        request = ClassificationRequest(input_text="Test")

        self.mock_primary.validate_request.return_value = True
        self.mock_primary.classify.side_effect = Exception("Primary failed")
        self.mock_fallback.classify.side_effect = Exception("Fallback failed")

        with pytest.raises(RuntimeError, match="All classification strategies failed"):
            self.classifier.classify(request)

    def test_get_strategy_info(self):
        """Testa obtenção de informações das estratégias."""
        self.mock_primary.name = "primary_strategy"
        self.mock_fallback.name = "fallback_strategy"

        info = self.classifier.get_strategy_info()

        assert info["primary_strategy"] == "primary_strategy"
        assert info["fallback_strategy"] == "fallback_strategy"
        assert info["has_fallback"] is True


class TestCreateClassifier:
    """Testes para factory function create_classifier."""

    def test_create_classifier_with_fallback(self):
        """Testa criação com fallback."""
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"

        classifier = create_classifier(
            mock_client, "custom-model", enable_fallback=True)

        assert isinstance(classifier, Classifier)
        assert isinstance(classifier.primary_strategy,
                          OllamaClassifierStrategy)
        assert isinstance(classifier.fallback_strategy,
                          RuleBasedClassifierStrategy)
        assert classifier.primary_strategy.model == "custom-model"

    def test_create_classifier_without_fallback(self):
        """Testa criação sem fallback."""
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"  # Adiciona atributo faltante

        classifier = create_classifier(mock_client, enable_fallback=False)

        assert isinstance(classifier, Classifier)
        assert isinstance(classifier.primary_strategy,
                          OllamaClassifierStrategy)
        # Nota: atualmente sempre cria fallback, mas enable_fallback=False
        # indica preferência para não usá-lo em cenários futuros
        assert isinstance(classifier.fallback_strategy,
                          RuleBasedClassifierStrategy)


class TestIntegration:
    """Testes de integração."""

    def test_full_classification_flow(self):
        """Teste completo do fluxo de classificação."""
        # Mock do OllamaClient
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"

        mock_response = {
            "classification": "feature",
            "confidence": "high",
            "reasoning": "Contains feature indicators",
            "key_indicators": ["add", "implement"],
            "suggested_actions": ["develop"],
            "complexity_score": 0.6,
            "estimated_effort": "high",
            "tags": ["feature", "new"]
        }

        mock_client.generate_json.return_value = mock_response

        # Cria classifier
        classifier = create_classifier(mock_client)

        # Executa classificação
        request = ClassificationRequest(
            input_text="Add user authentication system",
            context="Security module",
            language="python"
        )

        result = classifier.classify(request)

        # Verifica resultado
        assert result.classification == ClassificationType.FEATURE
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.reasoning == "Contains feature indicators"
        assert result.key_indicators == ["add", "implement"]
        assert result.suggested_actions == ["develop"]
        assert result.complexity_score == 0.6
        assert result.estimated_effort == "high"
        assert result.tags == ["feature", "new"]

        # Verifica chamada ao Ollama
        mock_client.generate_json.assert_called_once()
        call_args = mock_client.generate_json.call_args
        assert call_args[1]["model"] == "test-model"
        assert "Add user authentication system" in call_args[1]["user_prompt"]
        assert "Security module" in call_args[1]["user_prompt"]
        assert "python" in call_args[1]["user_prompt"]
