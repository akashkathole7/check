from audioop import add
import pandas as pd
import pickle
from sklearn.preprocessing import StandardScaler

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LinearRegression, Lasso, Ridge
from sklearn.metrics import mean_squared_error

import xgboost as xgb

from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
from hyperopt.pyll import scope

import mlflow

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("solar experiment")

def read_dataframe(filename):
    if filename.endswith('.csv'):
        df = pd.read_csv(filename)

  
    elif filename.endswith('.parquet'):
        df = pd.read_parquet(filename)
    
    return df

def add_features(train_path="/home/akash/Documents/programming/luminous hackathon ppt/Luminous MLOps/01-intro/Solar Power Plant Data.csv",
                 val_path="/home/akash/Documents/programming/luminous hackathon ppt/Luminous MLOps/01-intro/Solar Power Plant Data.csv"):
    df_train = read_dataframe(train_path)
    df_val = read_dataframe(val_path)

    print(len(df_train))
    print(len(df_val))

    # df_train['PU_DO'] = df_train['PULocationID'] + '_' + df_train['DOLocationID']
    # df_val['PU_DO'] = df_val['PULocationID'] + '_' + df_val['DOLocationID']

    # categorical = ['PU_DO'] #'PULocationID', 'DOLocationID']
    numerical = ['trip_distance']

    numerical = ['WindSpeed', 'Sunshine', 'AirPressure', 'Radiation', 'AirTemperature', 'RelativeAirHumidity']
    dv = StandardScaler()

    train_dicts = df_train[numerical]
    X_train = dv.fit_transform(train_dicts)

    val_dicts = df_val[numerical]
    X_val = dv.transform(val_dicts)

    target = 'SystemProduction'
    y_train = df_train[target].values
    y_val = df_val[target].values

    return X_train, X_val, y_train, y_val, dv

# # Modelling

# lr = LinearRegression()
# lr.fit(X_train, y_train)

# y_pred = lr.predict(X_val)

# mean_squared_error(y_val, y_pred, squared=False)

# with open('models/lin_reg.bin', 'wb') as f_out:
#     pickle.dump((dv, lr), f_out)

# with mlflow.start_run():

#     mlflow.set_tag("developer", "cristian")

#     mlflow.log_param("train-data-path", "./data/green_tripdata_2021-01.csv")
#     mlflow.log_param("valid-data-path", "./data/green_tripdata_2021-02.csv")

#     alpha = 0.1
#     mlflow.log_param("alpha", alpha)
#     lr = Lasso(alpha)
#     lr.fit(X_train, y_train)

#     y_pred = lr.predict(X_val)
#     rmse = mean_squared_error(y_val, y_pred, squared=False)
#     mlflow.log_metric("rmse", rmse)

#     mlflow.log_artifact(local_path="models/lin_reg.bin", artifact_path="models_pickle")

def train_model_search(train, valid, y_val):
    def objective(params):
        with mlflow.start_run():
            mlflow.set_tag("model", "xgboost")
            mlflow.log_params(params)
            booster = xgb.train(
                params=params,
                dtrain=train,
                num_boost_round=100,
                evals=[(valid, 'validation')],
                early_stopping_rounds=50
            )
            y_pred = booster.predict(valid)
            rmse = mean_squared_error(y_val, y_pred, squared=False)
            mlflow.log_metric("rmse", rmse)

        return {'loss': rmse, 'status': STATUS_OK}

    search_space = {
        'max_depth': scope.int(hp.quniform('max_depth', 4, 100, 1)),
        'learning_rate': hp.loguniform('learning_rate', -3, 0),
        'reg_alpha': hp.loguniform('reg_alpha', -5, -1),
        'reg_lambda': hp.loguniform('reg_lambda', -6, -1),
        'min_child_weight': hp.loguniform('min_child_weight', -1, 3),
        'objective': 'reg:linear',
        'seed': 42
    }

    best_result = fmin(
        fn=objective,
        space=search_space,
        algo=tpe.suggest,
        max_evals=1,
        trials=Trials()
    )
    return

def train_best_model(train, valid, y_val, dv):
    with mlflow.start_run():
        
        train = xgb.DMatrix(X_train, label=y_train)
        valid = xgb.DMatrix(X_val, label=y_val)

        best_params = {
            'learning_rate': 0.09585355369315604,
            'max_depth': 30,
            'min_child_weight': 1.060597050922164,
            'objective': 'reg:linear',
            'reg_alpha': 0.018060244040060163,
            'reg_lambda': 0.011658731377413597,
            'seed': 42
        }

        mlflow.log_params(best_params)

        booster = xgb.train(
            params=best_params,
            dtrain=train,
            num_boost_round=1000,
            evals=[(valid, 'validation')],
            early_stopping_rounds=50
        )

        y_pred = booster.predict(valid)
        rmse = mean_squared_error(y_val, y_pred, squared=False)
        mlflow.log_metric("rmse", rmse)

        with open("/home/akash/Documents/programming/luminous hackathon ppt/Luminous MLOps/03-orchestration/models/preprocessor.b", "wb") as f_out:
            pickle.dump(dv, f_out)
        mlflow.log_artifact("/home/akash/Documents/programming/luminous hackathon ppt/Luminous MLOps/03-orchestration/models/preprocessor.b", artifact_path="preprocessor")

        mlflow.xgboost.log_model(booster, artifact_path="models_mlflow")

if __name__ == "__main__":
    X_train, X_val, y_train, y_val, dv = add_features()
    train = xgb.DMatrix(X_train, label=y_train)
    valid = xgb.DMatrix(X_val, label=y_val)
    train_model_search(train, valid, y_val)
    train_best_model(train, valid, y_val, dv)