from auto_retrain import ModelRetrainer, PocketOptionAPI

if __name__ == "__main__":
    api = PocketOptionAPI()
    retrainer = ModelRetrainer(api)
    retrainer.retrain_model()
