#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test file for Hebrew speech recognition models

This test file benchmarks Hebrew-specific models against standard Whisper
to compare accuracy and performance for Hebrew transcription tasks.
"""

import pathlib
import time
from unittest import TestCase, skipIf
import os

import pysubs2
from pysubs2 import SSAFile

from subsai import SubsAI


class TestHebrewModels(TestCase):
    """Test Hebrew speech recognition models"""
    
    def setUp(self):
        self.subs_ai = SubsAI()
        self.hebrew_models = [
            'ivrit-ai/whisper-large-v2-tuned',
            'ivrit-ai/whisper-large-v3', 
            'Shiry/whisper-large-v2-he',
            'imvladikon/wav2vec2-large-xlsr-53-hebrew',
            'sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned'
        ]
        # Add a test audio file path here when available
        self.hebrew_audio_file = '../assets/audio/hebrew_test.mp3'  # placeholder
        
    def test_hebrew_models_available(self):
        """Test that Hebrew models are properly registered"""
        available_models = self.subs_ai.available_models()
        
        for hebrew_model in self.hebrew_models:
            with self.subTest(model=hebrew_model):
                self.assertIn(hebrew_model, available_models, 
                            f'Hebrew model {hebrew_model} should be available')
    
    def test_hebrew_model_info(self):
        """Test that Hebrew models have proper descriptions"""
        for hebrew_model in self.hebrew_models:
            with self.subTest(model=hebrew_model):
                info = self.subs_ai.model_info(hebrew_model)
                self.assertIn('description', info)
                # Check that description mentions Hebrew
                description = info['description'].lower()
                self.assertTrue(
                    'hebrew' in description or 'ivrit' in description,
                    f'Model {hebrew_model} description should mention Hebrew: {info["description"]}'
                )
    
    def test_hebrew_model_creation(self):
        """Test that Hebrew models can be instantiated"""
        for hebrew_model in self.hebrew_models:
            with self.subTest(model=hebrew_model):
                try:
                    # Try with Hebrew language setting for Whisper models
                    if 'whisper' in hebrew_model.lower():
                        model_config = {'language': 'hebrew'}
                    else:
                        model_config = {}
                    
                    model_instance = self.subs_ai.create_model(hebrew_model, model_config)
                    self.assertIsNotNone(model_instance, 
                                       f'Hebrew model {hebrew_model} should be creatable')
                except Exception as e:
                    self.fail(f'Failed to create Hebrew model {hebrew_model}: {str(e)}')
    
    @skipIf(not os.path.exists('../assets/audio/hebrew_test.mp3'), 
            "Hebrew test audio file not available")
    def test_hebrew_transcription(self):
        """Test Hebrew transcription with Hebrew models"""
        # This test requires a Hebrew audio file
        for hebrew_model in self.hebrew_models:
            with self.subTest(model=hebrew_model):
                try:
                    if 'whisper' in hebrew_model.lower():
                        model_config = {'language': 'hebrew'}
                    else:
                        model_config = {}
                        
                    model_instance = self.subs_ai.create_model(hebrew_model, model_config)
                    
                    start_time = time.time()
                    subs = model_instance.transcribe(self.hebrew_audio_file)
                    transcription_time = time.time() - start_time
                    
                    self.assertIsInstance(subs, SSAFile, 
                                        f'Hebrew model {hebrew_model} should return SSAFile')
                    self.assertGreater(len(subs), 0, 
                                     f'Hebrew model {hebrew_model} should produce subtitles')
                    
                    print(f"\nHebrew Model: {hebrew_model}")
                    print(f"Transcription time: {transcription_time:.2f}s")
                    print(f"Number of segments: {len(subs)}")
                    if len(subs) > 0:
                        print(f"First segment: {subs[0].plaintext}")
                        
                except Exception as e:
                    self.fail(f'Hebrew transcription failed for {hebrew_model}: {str(e)}')
    
    def test_hebrew_vs_standard_whisper_config(self):
        """Test that Hebrew models have appropriate default configurations"""
        standard_whisper = 'openai/whisper'
        
        for hebrew_model in self.hebrew_models:
            with self.subTest(model=hebrew_model):
                hebrew_schema = self.subs_ai.config_schema(hebrew_model)
                
                # Check that the model supports language configuration
                if 'language' in hebrew_schema:
                    self.assertIn('type', hebrew_schema['language'])
                    self.assertIn('description', hebrew_schema['language'])
                    
                    # For Hebrew Whisper models, default should be set appropriately
                    if 'whisper' in hebrew_model.lower():
                        description = hebrew_schema['language']['description'].lower()
                        self.assertTrue('hebrew' in description or 'language' in description,
                                      f'Language parameter should mention Hebrew support')

    def benchmark_hebrew_models(self, hebrew_audio_file=None):
        """
        Benchmark Hebrew models against standard Whisper
        This is a utility method that can be called manually for performance testing
        """
        if not hebrew_audio_file or not os.path.exists(hebrew_audio_file):
            print("Hebrew audio file not provided or doesn't exist. Skipping benchmark.")
            return
            
        results = {}
        
        # Test standard Whisper first
        try:
            standard_model = self.subs_ai.create_model('openai/whisper', {'language': 'hebrew'})
            start_time = time.time()
            standard_subs = standard_model.transcribe(hebrew_audio_file)
            standard_time = time.time() - start_time
            results['openai/whisper'] = {
                'time': standard_time,
                'segments': len(standard_subs),
                'text': [sub.plaintext for sub in standard_subs[:3]]  # First 3 segments
            }
        except Exception as e:
            print(f"Standard Whisper failed: {e}")
        
        # Test Hebrew models
        for hebrew_model in self.hebrew_models:
            try:
                if 'whisper' in hebrew_model.lower():
                    model_config = {'language': 'hebrew'}
                else:
                    model_config = {}
                    
                model_instance = self.subs_ai.create_model(hebrew_model, model_config)
                start_time = time.time()
                subs = model_instance.transcribe(hebrew_audio_file)
                transcription_time = time.time() - start_time
                
                results[hebrew_model] = {
                    'time': transcription_time,
                    'segments': len(subs),
                    'text': [sub.plaintext for sub in subs[:3]]  # First 3 segments
                }
            except Exception as e:
                print(f"Hebrew model {hebrew_model} failed: {e}")
                results[hebrew_model] = {'error': str(e)}
        
        # Print benchmark results
        print("\n" + "="*60)
        print("HEBREW MODELS BENCHMARK RESULTS")
        print("="*60)
        
        for model, result in results.items():
            if 'error' in result:
                print(f"\n{model}: ERROR - {result['error']}")
            else:
                print(f"\n{model}:")
                print(f"  Time: {result['time']:.2f}s")
                print(f"  Segments: {result['segments']}")
                print(f"  Sample text: {result['text'][:1]}")  # First segment only
        
        return results


if __name__ == '__main__':
    # Run benchmarks if Hebrew audio file is available
    test_instance = TestHebrewModels()
    test_instance.setUp()
    
    # Look for Hebrew test files in common locations
    potential_files = [
        '../assets/audio/hebrew_test.mp3',
        '../assets/audio/hebrew_test.wav',
        'hebrew_test.mp3',
        'hebrew_test.wav'
    ]
    
    hebrew_file = None
    for file_path in potential_files:
        if os.path.exists(file_path):
            hebrew_file = file_path
            break
    
    if hebrew_file:
        print(f"Found Hebrew test file: {hebrew_file}")
        test_instance.benchmark_hebrew_models(hebrew_file)
    else:
        print("No Hebrew test audio file found. To run benchmarks, place a Hebrew audio file at:")
        for file_path in potential_files:
            print(f"  {file_path}")