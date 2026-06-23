import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { fetchJson, setDataStore, getDataStore, clearCache } from './loader';

describe('loader', () => {
  beforeEach(() => {
    clearCache();
  });

  afterEach(() => {
    clearCache();
  });

  describe('getDataStore', () => {
    it('should return empty object initially', () => {
      expect(getDataStore()).toEqual({});
    });
  });

  describe('setDataStore', () => {
    it('should set the data store', () => {
      const testData = { key1: 'value1', key2: { nested: 'value' } };
      setDataStore(testData);
      expect(getDataStore()).toEqual(testData);
    });
  });

  describe('clearCache', () => {
    it('should clear the data store', () => {
      const testData = { key1: 'value1' };
      setDataStore(testData);
      expect(getDataStore()).toEqual(testData);
      
      clearCache();
      expect(getDataStore()).toEqual({});
    });
  });

  describe('fetchJson', () => {
    it('should return data from data store', async () => {
      const testData = { name: 'test', value: 123 };
      setDataStore({ 'data/test.json': testData });
      
      const result = await fetchJson<{ name: string; value: number }>('test.json');
      expect(result).toEqual(testData);
    });

    it('should handle runId parameter', async () => {
      const testData = { symbol: 'DCE.m2509' };
      setDataStore({ 'r1/data/test.json': testData });
      
      const result = await fetchJson<{ symbol: string }>('test.json', 1);
      expect(result).toEqual(testData);
    });

    it('should throw error if data not found', async () => {
      await expect(fetchJson('notfound.json')).rejects.toThrow();
    });

    it('should throw error if JSON is invalid', async () => {
      setDataStore({ 'invalid.json': 'not valid json' });
      await expect(fetchJson('invalid.json')).rejects.toThrow();
    });
  });
});