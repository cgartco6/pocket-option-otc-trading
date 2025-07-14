from auto_retrain import ModelRetrainer, PocketOptionAPI, POCKET_EMAIL, POCKET_PASSWORD, POCKET_API_KEY

if __name__ == "__main__":
    api_client = PocketOptionAPI(POCKET_EMAIL, POCKET_PASSWORD, POCKET_API_KEY)
    retrainer = ModelRetrainer(api_client)
    retrainer.retrain_model()
