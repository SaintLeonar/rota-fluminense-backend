def calcular_media(avaliacoes):
    """Calcula a média das avaliações.

    Args:
        avaliacoes (list): Lista de objetos Avaliacao.

    Returns:
        tuple: Média e total de avaliações.
    """
    if not avaliacoes:
        return None, 0

    notas = [avaliacao.nota for avaliacao in avaliacoes]
    total_avaliacoes = len(notas)
    media = round(sum(notas) / total_avaliacoes, 1) if notas else None

    return media, total_avaliacoes
