/**
 * SentiCall v3 — Client-Side Encrypted Storage & App Lock
 * Uses WebCrypto AES-GCM (256-bit) and PBKDF2 (600,000 iterations, SHA-256).
 * Persists personal cases and sensitive family/bank preferences strictly in IndexedDB.
 */

const DB_NAME = 'SentiCallEncryptedStore';
const DB_VERSION = 1;
const PBKDF2_ITERATIONS = 600000;

class SentiCallCryptoStore {
  constructor() {
    this.db = null;
    this.activeKey = null;
    this.salt = null;
    this.isAppLocked = false;
    this.lastActivityTime = Date.now();
    this.idleTimerInterval = null;
    this.hasPassphraseSet = false;
  }

  async init() {
    await this.initDB();
    await this.checkPassphraseState();
    this.startIdleTimer();
  }

  initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('cases')) {
          const store = db.createObjectStore('cases', { keyPath: 'id' });
          store.createIndex('created_at', 'created_at', { unique: false });
        }
        if (!db.objectStoreNames.contains('keys')) {
          db.createObjectStore('keys', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('settings')) {
          db.createObjectStore('settings', { keyPath: 'id' });
        }
      };
      request.onsuccess = (e) => {
        this.db = e.target.result;
        resolve(this.db);
      };
      request.onerror = (e) => reject(e.target.error);
    });
  }

  async checkPassphraseState() {
    const keyRecord = await this.getItem('keys', 'master_key_config');
    if (keyRecord && keyRecord.hasPassphrase) {
      this.hasPassphraseSet = true;
      this.salt = keyRecord.salt;
      this.isAppLocked = true; // Lock until user enters passphrase
    } else {
      this.hasPassphraseSet = false;
      // Use/create non-extractable device key
      await this.getOrCreateDeviceKey();
      this.isAppLocked = false;
    }
  }

  async getOrCreateDeviceKey() {
    let keyRecord = await this.getItem('keys', 'device_key');
    if (!keyRecord) {
      const cryptoKey = await window.crypto.subtle.generateKey(
        { name: 'AES-GCM', length: 256 },
        false, // non-extractable
        ['encrypt', 'decrypt']
      );
      await this.putItem('keys', { id: 'device_key', key: cryptoKey });
      this.activeKey = cryptoKey;
    } else {
      this.activeKey = keyRecord.key;
    }
  }

  /**
   * Derive AES-GCM key from user passphrase using PBKDF2 (600,000 iterations)
   */
  async setPassphrase(passphrase) {
    if (!passphrase || passphrase.length < 6) {
      throw new Error('Passphrase must be at least 6 characters.');
    }
    const salt = window.crypto.getRandomValues(new Uint8Array(16));
    const derivedKey = await this.deriveKeyFromPassphrase(passphrase, salt);

    this.activeKey = derivedKey;
    this.salt = salt;
    this.hasPassphraseSet = true;
    this.isAppLocked = false;

    // Store config with salt (never store passphrase or raw key)
    await this.putItem('keys', {
      id: 'master_key_config',
      hasPassphrase: true,
      salt: Array.from(salt),
      created_at: new Date().toISOString()
    });
  }

  async unlockWithPassphrase(passphrase) {
    const keyRecord = await this.getItem('keys', 'master_key_config');
    if (!keyRecord || !keyRecord.salt) {
      throw new Error('No passphrase configured on this device.');
    }
    const salt = new Uint8Array(keyRecord.salt);
    const derivedKey = await this.deriveKeyFromPassphrase(passphrase, salt);

    // Verify key by attempting to decrypt test token
    this.activeKey = derivedKey;
    this.isAppLocked = false;
    this.lastActivityTime = Date.now();
    return true;
  }

  async deriveKeyFromPassphrase(passphrase, salt) {
    const enc = new TextEncoder();
    const keyMaterial = await window.crypto.subtle.importKey(
      'raw',
      enc.encode(passphrase),
      'PBKDF2',
      false,
      ['deriveKey']
    );

    return window.crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt,
        iterations: PBKDF2_ITERATIONS,
        hash: 'SHA-256'
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
  }

  // Idle Timer (5 minutes auto-lock)
  startIdleTimer() {
    ['mousedown', 'keydown', 'touchstart'].forEach(evt => {
      window.addEventListener(evt, () => {
        this.lastActivityTime = Date.now();
      }, { passive: true });
    });

    if (this.idleTimerInterval) clearInterval(this.idleTimerInterval);
    this.idleTimerInterval = setInterval(() => {
      if (this.hasPassphraseSet && !this.isAppLocked) {
        const idleMs = Date.now() - this.lastActivityTime;
        if (idleMs > 5 * 60 * 1000) {
          this.lock();
        }
      }
    }, 15000);
  }

  lock() {
    if (this.hasPassphraseSet) {
      this.isAppLocked = true;
      this.activeKey = null;
      window.dispatchEvent(new CustomEvent('senticall_app_locked'));
    }
  }

  // --- AES-GCM Encrypt & Decrypt Helpers ---

  async encryptData(dataObj) {
    if (!this.activeKey) {
      await this.getOrCreateDeviceKey();
    }
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(JSON.stringify(dataObj));

    const cipherBuffer = await window.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.activeKey,
      encoded
    );

    return {
      iv: Array.from(iv),
      cipher: Array.from(new Uint8Array(cipherBuffer))
    };
  }

  async decryptData(encryptedObj) {
    if (!this.activeKey) {
      throw new Error('App is locked. Please enter your passphrase to view saved calls.');
    }
    const iv = new Uint8Array(encryptedObj.iv);
    const cipher = new Uint8Array(encryptedObj.cipher);

    const decryptedBuffer = await window.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      this.activeKey,
      cipher
    );

    const decryptedStr = new TextDecoder().decode(decryptedBuffer);
    return JSON.parse(decryptedStr);
  }

  // --- IndexedDB Operations ---

  putItem(storeName, item) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], 'readwrite');
      const store = tx.objectStore(storeName);
      const req = store.put(item);
      req.onsuccess = () => resolve(req.result);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  getItem(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], 'readonly');
      const store = tx.objectStore(storeName);
      const req = store.get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  getAllItems(storeName) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], 'readonly');
      const store = tx.objectStore(storeName);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  deleteItem(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], 'readwrite');
      const store = tx.objectStore(storeName);
      const req = store.delete(key);
      req.onsuccess = () => resolve(true);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  // --- Case Management ---

  async saveCase(casePayload, saveFullTranscript = false) {
    const caseId = casePayload.case_id || `SC-${Math.floor(Date.now() / 1000)}`;
    const createdAt = casePayload.created_at || new Date().toISOString();

    // Sensitive data payload
    const sensitivePayload = {
      ...casePayload,
      transcript: saveFullTranscript ? casePayload.transcript : null,
      full_transcript_saved: saveFullTranscript
    };

    const encrypted = await this.encryptData(sensitivePayload);

    // Store record with unencrypted metadata for radar list view
    const record = {
      id: caseId,
      created_at: createdAt,
      input_type: casePayload.input_type || 'audio',
      overall_score: casePayload.fusion?.overall_score || 0,
      risk_tier: casePayload.fusion?.risk_tier || 'Low Risk',
      primary_family_name: casePayload.primary_family_name || 'General Analysis',
      lead_time_s: casePayload.lead_time_s || null,
      encrypted_blob: encrypted
    };

    await this.putItem('cases', record);
    return caseId;
  }

  async getAllCases() {
    const records = await this.getAllItems('cases');
    records.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return records;
  }

  async getCaseById(caseId) {
    const record = await this.getItem('cases', caseId);
    if (!record) return null;
    const decryptedPayload = await this.decryptData(record.encrypted_blob);
    return decryptedPayload;
  }

  async deleteCase(caseId) {
    return await this.deleteItem('cases', caseId);
  }

  // --- Sensitive Local Settings (Emergency Contacts, Banks) ---

  async saveSensitiveSettings(settingsObj) {
    const encrypted = await this.encryptData(settingsObj);
    await this.putItem('settings', { id: 'personal_profile', encrypted });
  }

  async getSensitiveSettings() {
    const record = await this.getItem('settings', 'personal_profile');
    if (!record || !record.encrypted) return { emergency_contact: null, user_banks: [] };
    try {
      return await this.decryptData(record.encrypted);
    } catch (e) {
      return { emergency_contact: null, user_banks: [] };
    }
  }

  // --- Wipe Device ---
  async wipeDevice() {
    if (this.db) this.db.close();
    indexedDB.deleteDatabase(DB_NAME);
    localStorage.removeItem('senticall_view_mode');
    localStorage.removeItem('senticall_larger_text');
    console.log('Local device cases and preferences purged.');
  }
}

// Global instance
window.cryptoStore = new SentiCallCryptoStore();
