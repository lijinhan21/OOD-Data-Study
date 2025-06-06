# -*- coding: utf-8 -*-

"""
Unbalanced Four-Environment Folktables dataset implementation for IRM experiments.
"""

import os
import numpy as np
import torch
from sklearn.model_selection import train_test_split

import folktables
from folktables import ACSDataSource

from .base import BaseFolktablesDataset

class FourEnvSyntheticFolktables(BaseFolktablesDataset):
    """
    Unbalanced Four-Environment Folktables dataset that creates environments based on 
    the cross-product of SEX (Male/Female) and Income (Low/High) while preserving 
    the original distribution without balancing.
    
    Environment mapping:
    - Env 0: Male + Low Income (original counts)
    - Env 1: Male + High Income (original counts)
    - Env 2: Female + Low Income (original counts)
    - Env 3: Female + High Income (original counts)
    
    This dataset is designed for testing CategoryReweightedERM method.
    
    Args:
        root: Root directory of dataset where data will be stored
        env: Which environment to load ('train', 'val', 'test', or 'all_train')
        transform: A function/transform that takes in features and returns transformed features
        target_transform: A function/transform that takes in the target and transforms it
    """
    
    def __init__(self, root='./data', env='train', transform=None, target_transform=None):
        super().__init__(root, env, transform, target_transform)
        self.prepare_four_env_folktables()
        
        if env in ['train', 'val', 'test']:
            self.data_label_env_tuples = self._load_prepared_data('four_env_synthetic_folktables', env)
        elif env == 'all_train':
            self.data_label_env_tuples = self._load_prepared_data('four_env_synthetic_folktables', 'all_train')
        else:
            raise RuntimeError(f'{env} env unknown. Valid envs are train, val, test, and all_train')

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (features, target, env) where target is the income class and env is the environment (0-3)
        """
        features, target, env = self.data_label_env_tuples[index]

        if self.transform is not None:
            features = self.transform(features)

        if self.target_transform is not None:
            target = self.target_transform(target)

        return features, target, env

    def prepare_four_env_folktables(self):
        """Prepare the Unbalanced Four-Environment Folktables dataset."""
        if self._check_prepared_data('four_env_synthetic_folktables', ['train.pt', 'val.pt', 'test.pt']):
            print('Four-Environment Folktables dataset already exists')
            return

        print('Preparing Four-Environment Folktables dataset')
        
        # Define the problem
        ACSIncomeNew = folktables.BasicProblem(
            features=[
              'SCHL', 'OCCP', 'WKHP', 'SEX', 'AGEP',
            ],
            target='PINCP',
            target_transform=lambda x: x > 25000,
            group='SEX',
            preprocess=folktables.adult_filter,
            postprocess=lambda x: np.nan_to_num(x, -1),
        )

        # Get data from multiple states to have enough samples
        data_source = ACSDataSource(survey_year='2021', horizon='1-Year', survey='person')
        train_data = data_source.get_data(states=["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"], download=True)
        
        # Convert to numpy arrays
        features, labels, group = ACSIncomeNew.df_to_numpy(train_data)
        
        # Create indices by gender and income for training data
        # SEX: 1 for Male, 2 for Female in ACS data
        male_high_income_idx = np.where((group == 1) & (labels == 1))[0]
        male_low_income_idx = np.where((group == 1) & (labels == 0))[0]
        female_high_income_idx = np.where((group == 2) & (labels == 1))[0]
        female_low_income_idx = np.where((group == 2) & (labels == 0))[0]
        
        print(f"Original training data distribution:")
        print(f"Male low income: {len(male_low_income_idx)}")
        print(f"Male high income: {len(male_high_income_idx)}")
        print(f"Female low income: {len(female_low_income_idx)}")
        print(f"Female high income: {len(female_high_income_idx)}")
        
        male_low_income_idx = np.random.choice(male_low_income_idx, size=4000, replace=False)
        male_high_income_idx = np.random.choice(male_high_income_idx, size=16000, replace=False)
        female_low_income_idx = np.random.choice(female_low_income_idx, size=16000, replace=False)
        female_high_income_idx = np.random.choice(female_high_income_idx, size=4000, replace=False)
        
        # Create four environments using ALL available data (no balancing)
        # Env 0: Male + Low Income, Env 1: Male + High Income
        # Env 2: Female + Low Income, Env 3: Female + High Income
        
        np.random.seed(42)
        
        # Use ALL indices for each environment (keeping original distribution)
        env0_indices = male_low_income_idx
        env1_indices = male_high_income_idx
        env2_indices = female_low_income_idx
        env3_indices = female_high_income_idx
        
        # Combine all environments for training
        all_train_indices = np.concatenate([env0_indices, env1_indices, env2_indices, env3_indices])
        
        # Create environment labels
        env_labels = np.concatenate([
            np.zeros(len(env0_indices)),      # Env 0: Male + Low Income
            np.ones(len(env1_indices)),       # Env 1: Male + High Income  
            np.full(len(env2_indices), 2),    # Env 2: Female + Low Income
            np.full(len(env3_indices), 3)     # Env 3: Female + High Income
        ])
        
        # Shuffle the combined training data
        shuffle_indices = np.random.permutation(len(all_train_indices))
        all_train_indices = all_train_indices[shuffle_indices]
        env_labels = env_labels[shuffle_indices]
        
        # Extract features and labels for training
        train_features = features[all_train_indices]
        train_labels = labels[all_train_indices]
        train_group = group[all_train_indices]
        
        # Print environment distribution for verification
        print(f"\nUnbalanced training environment distribution:")
        for env_id in range(4):
            env_mask = (env_labels == env_id)
            env_features = train_features[env_mask]
            env_group = train_group[env_mask]
            env_targets = train_labels[env_mask]
            
            male_count = np.sum(env_group == 1)
            female_count = np.sum(env_group == 2)
            high_income_count = np.sum(env_targets == 1)
            low_income_count = np.sum(env_targets == 0)
            total_count = len(env_features)
            
            print(f"Env {env_id}: Total={total_count}, Male={male_count}, Female={female_count}, "
                  f"High Income={high_income_count}, Low Income={low_income_count}")
        
        # Convert training data to torch tensors
        train_features = torch.FloatTensor(train_features)
        train_labels = torch.LongTensor(train_labels)
        env_labels = torch.LongTensor(env_labels)
        
        # Split training data into train and validation sets while preserving environment distribution
        unique_envs = torch.unique(env_labels)
        train_indices_list = []
        val_indices_list = []
        
        for env_id in unique_envs:
            env_mask = env_labels == env_id
            env_indices = torch.where(env_mask)[0]
            
            # Split each environment separately to preserve distribution
            n_env_samples = len(env_indices)
            train_size = int(0.8 * n_env_samples)
            
            shuffled_env_indices = env_indices[torch.randperm(n_env_samples)]
            train_indices_list.append(shuffled_env_indices[:train_size])
            val_indices_list.append(shuffled_env_indices[train_size:])
        
        # Combine all train and val indices
        final_train_idx = torch.cat(train_indices_list)
        final_val_idx = torch.cat(val_indices_list)
        
        # Shuffle final indices
        final_train_idx = final_train_idx[torch.randperm(len(final_train_idx))]
        final_val_idx = final_val_idx[torch.randperm(len(final_val_idx))]
        
        train_data = (
            train_features[final_train_idx],
            train_labels[final_train_idx],
            env_labels[final_train_idx]
        )
        val_data = (
            train_features[final_val_idx],
            train_labels[final_val_idx],
            env_labels[final_val_idx]
        )
        
        # Load existing test data from synthetic_folktables instead of creating new one
        synthetic_test_path = os.path.join(self.root, 'synthetic_folktables', 'test.pt')
        if os.path.exists(synthetic_test_path):
            print("Loading existing test dataset from synthetic_folktables")
            loaded_test_data = torch.load(synthetic_test_path)
            test_features, test_labels, _ = loaded_test_data  # Ignore original env labels
            
            # Remap to 4 environments based on gender and income
            # Extract gender from features (SEX is at index 3, 1=Male, 2=Female)
            test_gender = test_features[:, 3]  # SEX feature
            
            # Create new environment labels based on gender and income
            test_env_labels = torch.zeros(len(test_features), dtype=torch.long)
            for i in range(len(test_features)):
                gender = test_gender[i].item()
                income = test_labels[i].item()
                if gender == 1 and income == 0:  # Male + Low Income
                    test_env_labels[i] = 0
                elif gender == 1 and income == 1:  # Male + High Income
                    test_env_labels[i] = 1
                elif gender == 2 and income == 0:  # Female + Low Income
                    test_env_labels[i] = 2
                elif gender == 2 and income == 1:  # Female + High Income
                    test_env_labels[i] = 3
            
            test_data = (test_features, test_labels, test_env_labels)
            
            print(f"Loaded test data with {len(test_features)} samples")
            
            # Print test environment distribution after remapping
            print(f"\nTest environment distribution (loaded from synthetic_folktables):")
            for env_id in range(4):
                env_mask = (test_env_labels == env_id)
                env_count = torch.sum(env_mask).item()
                if env_count > 0:
                    env_targets = test_labels[env_mask]
                    high_income_count = torch.sum(env_targets == 1).item()
                    low_income_count = torch.sum(env_targets == 0).item()
                    print(f"Env {env_id}: {env_count} samples (High Income: {high_income_count}, Low Income: {low_income_count})")
                else:
                    print(f"Env {env_id}: 0 samples")
        else:
            raise FileNotFoundError(f"Test dataset not found at {synthetic_test_path}. Please ensure synthetic_folktables dataset is prepared first.")
        
        # Create directory and save datasets
        four_env_dir = self._create_data_dir('four_env_synthetic_folktables')
        torch.save(train_data, os.path.join(four_env_dir, 'train.pt'))
        torch.save(val_data, os.path.join(four_env_dir, 'val.pt'))
        torch.save(test_data, os.path.join(four_env_dir, 'test.pt'))
        
        print(f"Four-Environment Folktables dataset created")
        print(f"Train: {len(train_data[0])} samples, Val: {len(val_data[0])} samples, Test: {len(test_data[0])} samples")
        
        # Print final environment distribution for all splits
        for split_name, split_data in [('Train', train_data), ('Val', val_data), ('Test', test_data)]:
            env_counts = torch.bincount(split_data[2], minlength=4)
            total_samples = len(split_data[0])
            percentages = [f"{count.item()}/{total_samples} ({100*count.item()/total_samples:.1f}%)" 
                          for count in env_counts]
            print(f"{split_name} environment distribution: Env0={percentages[0]}, Env1={percentages[1]}, "
                  f"Env2={percentages[2]}, Env3={percentages[3]}")
            
            # Print label distribution per environment for this split
            for env_id in range(4):
                env_mask = (split_data[2] == env_id)
                if env_mask.sum() > 0:
                    env_targets = split_data[1][env_mask]
                    high_income = torch.sum(env_targets == 1).item()
                    low_income = torch.sum(env_targets == 0).item()
                    total_env = env_mask.sum().item()
                    print(f"  {split_name} Env {env_id}: High Income={high_income}/{total_env} ({100*high_income/total_env:.1f}%), "
                          f"Low Income={low_income}/{total_env} ({100*low_income/total_env:.1f}%)") 