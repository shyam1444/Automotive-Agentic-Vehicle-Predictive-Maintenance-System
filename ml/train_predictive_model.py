"""
Train Predictive Maintenance ML Model
=====================================
Generates synthetic telemetry data and trains a failure prediction model.
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
import joblib
from loguru import logger
from datetime import datetime

# Configure logging
logger.add(
    "logs/ml_training_{time}.log",
    rotation="100 MB",
    retention="7 days",
    level="INFO"
)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL_OUTPUT_PATH = "models/vehicle_failure_model.pkl"
SAMPLES_NORMAL = 80000
SAMPLES_WARNING = 15000
SAMPLES_CRITICAL = 5000
RANDOM_SEED = 42

# Feature ranges for normal operation
NORMAL_RANGES = {
    'engine_rpm': (800, 4000),
    'engine_temp': (60, 95),
    'vibration': (0.5, 2.5),
    'speed': (0, 120),
    'fuel_level': (10, 100),
    'battery_voltage': (12.0, 14.5),
    'rolling_avg_rpm': (800, 4000),
    'rolling_avg_temp': (60, 95),
    'rolling_avg_vibration': (0.5, 2.5),
    'rolling_avg_speed': (0, 120)
}

# ============================================================================
# SYNTHETIC DATA GENERATION
# ============================================================================

def generate_normal_samples(n_samples: int) -> pd.DataFrame:
    """Generate normal operating condition samples"""
    np.random.seed(RANDOM_SEED)
    
    data = {
        'engine_rpm': np.random.uniform(
            NORMAL_RANGES['engine_rpm'][0],
            NORMAL_RANGES['engine_rpm'][1],
            n_samples
        ),
        'engine_temp': np.random.normal(80, 8, n_samples).clip(60, 95),
        'vibration': np.random.gamma(2, 0.5, n_samples).clip(0.5, 2.5),
        'speed': np.random.uniform(0, 120, n_samples),
        'fuel_level': np.random.uniform(10, 100, n_samples),
        'battery_voltage': np.random.normal(13.2, 0.4, n_samples).clip(12.0, 14.5),
        'rolling_avg_rpm': np.random.uniform(
            NORMAL_RANGES['rolling_avg_rpm'][0],
            NORMAL_RANGES['rolling_avg_rpm'][1],
            n_samples
        ),
        'rolling_avg_temp': np.random.normal(80, 6, n_samples).clip(60, 95),
        'rolling_avg_vibration': np.random.gamma(2, 0.5, n_samples).clip(0.5, 2.5),
        'rolling_avg_speed': np.random.uniform(0, 120, n_samples),
        'failure_event': 0  # Normal = 0
    }
    
    return pd.DataFrame(data)

def generate_warning_samples(n_samples: int) -> pd.DataFrame:
    """Generate warning condition samples (degraded performance)"""
    np.random.seed(RANDOM_SEED + 1)
    
    data = {
        'engine_rpm': np.random.uniform(4000, 5500, n_samples),  # High RPM
        'engine_temp': np.random.normal(100, 10, n_samples).clip(95, 120),  # Elevated temp
        'vibration': np.random.gamma(3, 1.0, n_samples).clip(2.5, 5.0),  # Increased vibration
        'speed': np.random.uniform(0, 140, n_samples),
        'fuel_level': np.random.uniform(5, 100, n_samples),
        'battery_voltage': np.random.normal(11.5, 0.8, n_samples).clip(10.0, 13.0),  # Lower voltage
        'rolling_avg_rpm': np.random.uniform(4000, 5500, n_samples),
        'rolling_avg_temp': np.random.normal(100, 8, n_samples).clip(95, 120),
        'rolling_avg_vibration': np.random.gamma(3, 1.0, n_samples).clip(2.5, 5.0),
        'rolling_avg_speed': np.random.uniform(0, 140, n_samples),
        'failure_event': 1  # Warning = 1
    }
    
    return pd.DataFrame(data)

def generate_critical_samples(n_samples: int) -> pd.DataFrame:
    """Generate critical/failure condition samples"""
    np.random.seed(RANDOM_SEED + 2)
    
    # Generate RPM - mix of stalling and over-revving
    rpm_stalling = np.random.uniform(200, 600, n_samples // 2)
    rpm_overrev = np.random.uniform(5500, 7000, n_samples // 2)
    engine_rpm = np.concatenate([rpm_stalling, rpm_overrev])
    np.random.shuffle(engine_rpm)
    engine_rpm = engine_rpm[:n_samples]
    
    # Generate rolling avg RPM (similar pattern)
    rpm_avg_stalling = np.random.uniform(200, 600, n_samples // 2)
    rpm_avg_overrev = np.random.uniform(5500, 7000, n_samples // 2)
    rolling_avg_rpm = np.concatenate([rpm_avg_stalling, rpm_avg_overrev])
    np.random.shuffle(rolling_avg_rpm)
    rolling_avg_rpm = rolling_avg_rpm[:n_samples]
    
    data = {
        'engine_rpm': engine_rpm,
        'engine_temp': np.random.normal(115, 15, n_samples).clip(105, 150),  # Overheating
        'vibration': np.random.gamma(5, 1.5, n_samples).clip(5.0, 15.0),  # Severe vibration
        'speed': np.random.uniform(0, 160, n_samples),
        'fuel_level': np.random.uniform(0, 20, n_samples),  # Low fuel
        'battery_voltage': np.random.normal(10.0, 1.2, n_samples).clip(8.0, 11.5),  # Critical voltage
        'rolling_avg_rpm': rolling_avg_rpm,
        'rolling_avg_temp': np.random.normal(115, 12, n_samples).clip(105, 150),
        'rolling_avg_vibration': np.random.gamma(5, 1.5, n_samples).clip(5.0, 15.0),
        'rolling_avg_speed': np.random.uniform(0, 160, n_samples),
        'failure_event': 1  # Critical = 1 (same as warning for binary classification)
    }
    
    return pd.DataFrame(data)

def generate_synthetic_dataset() -> pd.DataFrame:
    """Generate complete synthetic dataset"""
    logger.info("🎲 Generating synthetic dataset...")
    
    normal_df = generate_normal_samples(SAMPLES_NORMAL)
    logger.info(f"✅ Generated {SAMPLES_NORMAL} normal samples")
    
    warning_df = generate_warning_samples(SAMPLES_WARNING)
    logger.info(f"⚠️ Generated {SAMPLES_WARNING} warning samples")
    
    critical_df = generate_critical_samples(SAMPLES_CRITICAL)
    logger.info(f"🚨 Generated {SAMPLES_CRITICAL} critical samples")
    
    # Combine all samples
    full_dataset = pd.concat([normal_df, warning_df, critical_df], ignore_index=True)
    
    # Shuffle
    full_dataset = full_dataset.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
    
    logger.info(f"📊 Total dataset size: {len(full_dataset)} samples")
    logger.info(f"📊 Class distribution:\n{full_dataset['failure_event'].value_counts()}")
    
    return full_dataset

# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_model(df: pd.DataFrame) -> RandomForestClassifier:
    """Train Random Forest classifier"""
    logger.info("🤖 Starting model training...")
    
    # Prepare features and target
    feature_cols = [
        'engine_rpm', 'engine_temp', 'vibration', 'speed',
        'fuel_level', 'battery_voltage',
        'rolling_avg_rpm', 'rolling_avg_temp',
        'rolling_avg_vibration', 'rolling_avg_speed'
    ]
    
    X = df[feature_cols]
    y = df['failure_event']
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )
    
    logger.info(f"📐 Training set: {X_train.shape[0]} samples")
    logger.info(f"📐 Test set: {X_test.shape[0]} samples")
    
    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=RANDOM_SEED,
        n_jobs=-1,
        class_weight='balanced'
    )
    
    logger.info("🔄 Training Random Forest...")
    model.fit(X_train, y_train)
    logger.info("✅ Training complete!")
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    logger.info(f"📊 Model Performance:")
    logger.info(f"   Accuracy: {accuracy:.4f}")
    logger.info(f"   F1 Score: {f1:.4f}")
    
    logger.info(f"\n📋 Classification Report:\n{classification_report(y_test, y_pred)}")
    logger.info(f"\n🔢 Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info(f"\n🎯 Feature Importance:\n{feature_importance.to_string()}")
    
    return model

# ============================================================================
# MODEL PERSISTENCE
# ============================================================================

def save_model(model: RandomForestClassifier, path: str):
    """Save trained model to disk"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Save model with metadata
    model_data = {
        'model': model,
        'feature_names': [
            'engine_rpm', 'engine_temp', 'vibration', 'speed',
            'fuel_level', 'battery_voltage',
            'rolling_avg_rpm', 'rolling_avg_temp',
            'rolling_avg_vibration', 'rolling_avg_speed'
        ],
        'trained_at': datetime.now().isoformat(),
        'model_type': 'RandomForestClassifier',
        'version': '1.0.0'
    }
    
    joblib.dump(model_data, path)
    logger.info(f"💾 Model saved to: {path}")
    
    # Save feature names separately for reference
    feature_path = path.replace('.pkl', '_features.txt')
    with open(feature_path, 'w') as f:
        f.write('\n'.join(model_data['feature_names']))
    logger.info(f"📝 Feature names saved to: {feature_path}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main training pipeline"""
    logger.info("=" * 80)
    logger.info("🚀 Starting Predictive Maintenance Model Training")
    logger.info("=" * 80)
    
    try:
        # Generate synthetic data
        dataset = generate_synthetic_dataset()
        
        # Train model
        model = train_model(dataset)
        
        # Save model
        save_model(model, MODEL_OUTPUT_PATH)
        
        logger.info("=" * 80)
        logger.info("✅ Training pipeline completed successfully!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
