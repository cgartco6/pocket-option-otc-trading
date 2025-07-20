from auto_retrain import ModelRetrainer, PocketOptionAPI

if _name_ == "_main_":
    api = PocketOptionAPI()
    retrainer = ModelRetrainer(api)
    retrainer.retrain_model()
