import logging


class Logger:
    """
    Central logging setup for all modules.
    """

    @staticmethod
    def get_logger(name="verdesat"):
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(levelname)s %(asctime)s] %(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
