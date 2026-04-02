class AppError(Exception):
    def __init__(self, message, status_code=500):
        """Define uma Exceção Personalizada.

        Args:
            message (str): Mensagem de erro.
            status_code (int): Código de status HTTP.

        Returns:
            None
        """
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
