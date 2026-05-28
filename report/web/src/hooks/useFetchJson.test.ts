import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useFetchJson } from '../hooks/useFetchJson';
import { setDataStore, clearCache } from '../data/loader';

describe('useFetchJson', () => {
  beforeEach(() => {
    clearCache();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearCache();
  });

  it('should return loading state initially', () => {
    const { result } = renderHook(() => useFetchJson<{ name: string }>('test.json'));
    
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should load data successfully', async () => {
    const testData = { name: 'test', value: 123 };
    setDataStore({ 'data/test.json': testData });
    
    const { result } = renderHook(() => useFetchJson<{ name: string; value: number }>('test.json'));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toEqual(testData);
    expect(result.current.error).toBeNull();
  });

  it('should handle empty path', () => {
    const { result } = renderHook(() => useFetchJson<{ name: string }>(''));
    
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should handle runId parameter', async () => {
    const testData = { symbol: 'DCE.m2509' };
    setDataStore({ 'r1/data/test.json': testData });
    
    const { result } = renderHook(() => useFetchJson<{ symbol: string }>('test.json', 1));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toEqual(testData);
  });

  it('should handle error when data not found', async () => {
    const { result } = renderHook(() => useFetchJson<{ name: string }>('notfound.json'));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('should handle JSON parsing error', async () => {
    setDataStore({ 'invalid.json': 'not valid json' });
    
    const { result } = renderHook(() => useFetchJson<{ name: string }>('invalid.json'));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toBeNull();
    expect(result.current.error).not.toBeNull();
  });
});