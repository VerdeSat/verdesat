from analytics.timeseries import TimeSeries

class ForecastModel:
    """
    Abstract base for forecasting (Prophet, LSTM, etc).
    """
    def fit(self, timeseries: TimeSeries):
        raise NotImplementedError()
    def predict(self, periods: int):
        raise NotImplementedError()