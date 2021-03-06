# PL 0.5928

#Import modules
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import lightgbm as lgb
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.model_selection import train_test_split
from tqdm import tqdm
from sklearn.model_selection import KFold
sns.set_style("whitegrid")


#Import data
print('import data')
train_df = pd.read_csv('train.csv')
test_df = pd.read_csv('test.csv')
historical_data_df = pd.read_csv('historical_user_logs.csv')
submission_df = pd.read_csv('sample_submission.csv')


label_y = train_df['is_click']
del train_df['is_click']

#---------------------Preprocess Train set--------------------
print('train preprocess')
#Extract time
#train_df['hour'] = train_df['DateTime'].str.slice(11,13)
#train_df['hour'] = train_df['hour'].astype(int)

#Aggregate historical data features
del historical_data_df['DateTime']
# hist_agg_unique = historical_data_df.groupby('user_id').nunique()[['product', 'action']]
# hist_agg_unique.columns = ['product_nunique', 'action_nunique']
#
hist_agg_count = pd.DataFrame(historical_data_df.groupby('product').count())
#hist_agg_count.columns = ['visit_count']
hist_agg_count['popularity'] = hist_agg_count['action']/hist_agg_count['action'].sum()
hist_agg_count = hist_agg_count.drop(['user_id', 'action'], axis = 1)
#
# train_df = train_df.merge(right=hist_agg_unique.reset_index(), how='left', on='user_id')
# train_df = train_df.merge(right=hist_agg_count.reset_index(), how='left', on='user_id')

prod_interest = pd.crosstab(historical_data_df['product'], historical_data_df['action'], normalize='index')
prod_interest['interest'] = prod_interest['interest']*100
del prod_interest['view']

train_df = train_df.merge(right=prod_interest.reset_index(), how='left', on='product')
train_df = train_df.merge(right=hist_agg_count.reset_index(), how='left', on='product')

#Set as categorical the respectful variables
cat_cols = ['user_id', 'product', 'campaign_id',
            'webpage_id',
            'product_category_1',
            'product_category_2',
            'user_group_id',
            #'gender',
            'age_level',
            'user_depth',
            'city_development_index',
            'var_1',
            #'hour',
            ]

for col in cat_cols:
    train_df[col] = train_df[col].astype('category')
    train_df[col] = train_df[col].cat.codes

#Replace -1 with null
train_df[train_df==-1] = np.nan

#Drop unneeded features
train_df = train_df.drop(['session_id',
                          #'campaign_id',
                      'DateTime',
                      #'user_group_id',
                      #'hour',
                      'gender',
                      #'user_id',
                      #'product_category_2',
                      #'city_development_index',
                      #'age_level',
                      #'webpage_id'
                      #'visit_count'
                      ], axis=1)

#---------------------Preprocess Test set--------------------
print('test preprocess')
#Extract time
# test_df['hour'] = test_df['DateTime'].str.slice(11,13)
# test_df['hour'] = test_df['hour'].astype(int)

#Aggregate historical data features
#aggregations have been calculate in train set

# test_df = test_df.merge(right=hist_agg_unique.reset_index(), how='left', on='user_id')
# test_df = test_df.merge(right=hist_agg_count.reset_index(), how='left', on='user_id')

test_df = test_df.merge(right=prod_interest.reset_index(), how='left', on='product')
test_df = test_df.merge(right=hist_agg_count.reset_index(), how='left', on='product')


for col in cat_cols:
    test_df[col] = test_df[col].astype('category')
    test_df[col] = test_df[col].cat.codes

#Replace -1 with null
test_df[test_df==-1] = np.nan

#Drop unneeded features
test_df = test_df.drop(['session_id',
                        #'campaign_id',
                      'DateTime',
                      #'user_group_id',
                      #'hour',
                      'gender',
                      #'user_id',
                      #'product_category_2',
                      #'city_development_index',
                      #'age_level',
                      #'webpage_id'
                      #'visit_count'
                      ], axis=1)


# #Frequency encoding
# def frequency_encoding(frame, col):
#     freq_encoding = frame.groupby([col]).size()/frame.shape[0]
#     freq_encoding = freq_encoding.reset_index().rename(columns={0:'{}_Frequency'.format(col)})
#     return frame.merge(freq_encoding, on=col, how='left')
#
# len_train = train_df.shape[0]
# df_all = pd.concat([train_df, test_df])
#
# for col in tqdm(cat_cols):
#     df_all = frequency_encoding(df_all, col)
#
# train_df = df_all[:len_train]
# test_df = df_all[len_train:]

# quantile_list = [0, .25, .5, .75, 1.]
# percentile_list = [.1, .2, .3, .4, .5, .6, .7, .8, .9, .10]
# for col in [ 'interest', 'popularity', 'user_id_Frequency',
#              'product_Frequency', 'campaign_id_Frequency',
#              'product_category_1_Frequency', 'user_depth_Frequency']:
#     train_df[col+'_quantiles'] = pd.qcut(train_df[col], q=quantile_list, duplicates='drop')
#     test_df[col + '_quantiles'] = pd.qcut(test_df[col], q=quantile_list, duplicates='drop')
#     #train_df[col+'_percentiles'] = pd.qcut(train_df[col], q=percentile_list, duplicates='drop')
#     #test_df[col + '_percentiles'] = pd.qcut(test_df[col], q=percentile_list, duplicates='drop')


#Mean Encoding
train_df['target'] = label_y
def mean_k_fold_encoding(col, alpha):
    target_name = 'target'
    target_mean_global = train_df[target_name].mean()

    nrows_cat = train_df.groupby(col)[target_name].count()
    target_means_cats = train_df.groupby(col)[target_name].mean()
    target_means_cats_adj = (target_means_cats * nrows_cat +
                             target_mean_global * alpha) / (nrows_cat + alpha)
    # Mapping means to test data
    encoded_col_test = test_df[col].map(target_means_cats_adj)

    kfold = KFold(n_splits=5, shuffle=True, random_state=1989)
    parts = []
    for trn_inx, val_idx in kfold.split(train_df):
        df_for_estimation, df_estimated = train_df.iloc[trn_inx], train_df.iloc[val_idx]
        nrows_cat = df_for_estimation.groupby(col)[target_name].count()
        target_means_cats = df_for_estimation.groupby(col)[target_name].mean()

        target_means_cats_adj = (target_means_cats * nrows_cat +
                                 target_mean_global * alpha) / (nrows_cat + alpha)

        encoded_col_train_part = df_estimated[col].map(target_means_cats_adj)
        parts.append(encoded_col_train_part)

    encoded_col_train = pd.concat(parts, axis=0)
    encoded_col_train.fillna(target_mean_global, inplace=True)
    encoded_col_train.sort_index(inplace=True)

    return encoded_col_train, encoded_col_test


for col in tqdm(cat_cols):
    temp_encoded_tr, temp_encoded_te = mean_k_fold_encoding(col, 5)
    new_feat_name = 'mean_k_fold_{}'.format(col)
    train_df[new_feat_name] = temp_encoded_tr.values
    test_df[new_feat_name] = temp_encoded_te.values

del train_df['target']


oof_pred = np.zeros((test_df.shape[0], 8))

for i in range(8):
    #Split in train and validation set
    train_early_x, valid_early_x, train_early_y, valid_early_y = train_test_split(train_df, label_y, test_size=0.2, stratify=label_y)


    #------------------------Build LightGBM Model-----------------------
    train_data=lgb.Dataset(train_early_x,label=train_early_y)
    valid_data=lgb.Dataset(valid_early_x,label=valid_early_y)

    #Select Hyper-Parameters
    params = {'boosting_type': 'gbdt',
              'max_depth' : 6,
              'objective': 'binary',
              'nthread': 32,
              #'n_estimators': 244,
              'num_leaves': 12,
              'learning_rate': 0.02,
              #'max_bin': 512,
              #'subsample_for_bin': 200,
              #'subsample': 0.7,
              #'subsample_freq': 5,
              #'colsample_bytree': 0.9,
              'reg_alpha': 0.11,
              'reg_lambda': 0.1,
              #'min_child_weight': 0.9,
              #'min_child_samples': 5,
              #'scale_pos_weight': 1,
              #'num_class' : 2,
              'metric' : 'auc',
              'is_unbalance' : 'True'
              }

    # Encode categorical
    cat_cols = ['user_id',
                'product', 'campaign_id',
                #'webpage_id',
                #'product_category_1',
                'product_category_2',
                'user_group_id',
                # 'gender',
                'age_level',
                #'user_depth',
                #'city_development_index',
                'var_1',
                # 'hour',
                ]

    #Train model on selected parameters and number of iterations
    lgbm = lgb.train(params,
                     train_data,
                     4500,
                     categorical_feature=cat_cols,
                     early_stopping_rounds= 10,
                     valid_sets= [train_data, valid_data],
                     verbose_eval= 10
                     )

    #Predict on test set
    predictions_lgbm_prob = lgbm.predict(test_df, num_iteration=lgbm.best_iteration)
    predictions_lgbm_01 = np.where(predictions_lgbm_prob > 0.5, 1, 0) #Turn probability to 0-1 binary output
    plt.hist(predictions_lgbm_prob)
    print('Ratio:', predictions_lgbm_01.sum()/len(predictions_lgbm_01))
    oof_pred[:,i] = predictions_lgbm_prob

final_pred = oof_pred.mean(axis = 1)

#--------------------------Print accuracy measures and variable importances----------------------
#Plot Variable Importances
lgb.plot_importance(lgbm, max_num_features=21, importance_type='gain')

submission_df.is_click = final_pred
submission_df.to_csv('lgb_4_FE_kfold_5.csv', index = False)