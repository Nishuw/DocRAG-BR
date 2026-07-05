"""Testes do coracao do produto: o verificador numerico e o parser do auditor.

Rodar: python -m unittest discover tests -v
"""
import unittest

from src.verification.auditor import _parse_findings
from src.verification.verifier import annotate_answer, extract_numbers, verify_answer


def _chunk(content: str) -> dict:
    return {"content": content, "type": "text", "source": "doc.pdf", "page": 1}


class TestExtractNumbers(unittest.TestCase):
    def test_formatos_brasileiros(self):
        nums = extract_numbers("Lucro de R$ 61.412 milhoes, margem de 4,2% e alta de 61,4.")
        values = {n["value"] for n in nums}
        self.assertEqual(values, {61412.0, 4.2, 61.4})

    def test_ignora_trimestres_e_citacoes(self):
        nums = extract_numbers(
            "No 1T26, o EBITDA subiu [doc.pdf, pag. 12] conforme o 4T25."
        )
        self.assertEqual(nums, [])

    def test_ignora_inteiros_pequenos_soltos(self):
        nums = extract_numbers("A busca tem 2 estagios e retorna top 4 chunks.")
        self.assertEqual(nums, [])

    def test_moeda_marca_inteiro_pequeno_como_significativo(self):
        nums = extract_numbers("Dividendos de R$ 9 bilhoes.")
        self.assertEqual([n["value"] for n in nums], [9.0])


class TestVerifyAnswer(unittest.TestCase):
    FONTE = _chunk("Fluxo de caixa operacional de R$ 43.975 milhoes no trimestre (queda de 19,9%).")

    def test_numero_confirmado_na_fonte(self):
        v = verify_answer("O FCO foi de R$ 43.975 milhoes.", [self.FONTE])
        self.assertEqual((v["confirmed"], v["total"]), (1, 1))

    def test_alucinacao_e_flagrada(self):
        v = verify_answer("O FCO foi de R$ 99.999 milhoes.", [self.FONTE])
        self.assertEqual((v["confirmed"], v["total"]), (0, 1))

    def test_annotate_insere_selos(self):
        v = verify_answer("Queda de 19,9% e FCO de R$ 88.888.", [self.FONTE])
        annotated = annotate_answer("Queda de 19,9% e FCO de R$ 88.888.", v["numbers"])
        self.assertIn("19,9%✅", annotated)
        self.assertIn("88.888⚠️", annotated)


class TestAuditorParser(unittest.TestCase):
    def test_json_com_cerca_de_codigo(self):
        raw = """```json
        [{"titulo": "T", "severidade": "alerta", "descoberta": "D", "arquivo": "a.pdf", "pagina": "4", "trecho": "x"}]
        ```"""
        findings = _parse_findings(raw)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["pagina"], 4)  # coercao de string p/ int

    def test_json_invalido_retorna_vazio(self):
        self.assertEqual(_parse_findings("nao sou json"), [])

    def test_item_sem_descoberta_e_descartado(self):
        findings = _parse_findings('[{"titulo": "so titulo"}]')
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
