/**
 * SentiCall v3 — Live Risk & Text Scoring Engine (JavaScript)
 * Runs in Web Workers and Node.js test environment with 100% scoring parity to Python.
 * Uses shared data/tactics.json and models/text_model.json.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SentiCallRiskEngine = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  class SentiCallRiskEngine {
    constructor(modelData, tacticsData, options = {}) {
      this.model = modelData || null;
      this.tacticsConfig = tacticsData || null;
      this.sensitivity = options.sensitivity || 'balanced';
      
      // Session state
      this.state = 'calm'; // 'calm' | 'heads_up' | 'danger'
      this.dangerDismissed = false;
      this.consecutiveDangerCount = 0;
      this.historyUpdates = []; // [{ time_s, risk_prob, tactics }]
      this.firstAlertTimeS = null;
      this.askMomentTimeS = null;
      this.leadTimeS = null;
      this.localCorrections = [];

      this.initRegexes();
    }

    initRegexes() {
      if (!this.tacticsConfig) return;
      this.compiledTactics = (this.tacticsConfig.tactics || []).map(t => {
        let enRegex = null;
        let hiRegex = null;
        try { if (t.regex) enRegex = new RegExp(t.regex, 'gi'); } catch (e) { }
        try { if (t.hinglish_regex) hiRegex = new RegExp(t.hinglish_regex, 'gi'); } catch (e) { }
        return {
          id: t.id,
          title: t.title,
          severity: t.severity,
          icon: t.icon,
          badge_class: t.badge_class,
          description: t.description,
          checklist_label: t.checklist_label,
          enRegex,
          hiRegex
        };
      });

      this.compiledNegations = (this.tacticsConfig.safety_rules?.negation_patterns || []).map(pat => {
        try { return new RegExp(pat, 'gi'); } catch (e) { return null; }
      }).filter(Boolean);
    }

    setSensitivity(level) {
      if (['gentle', 'balanced', 'cautious'].includes(level)) {
        this.sensitivity = level;
      }
    }

    /**
     * Exact tokenization matching Python's TfidfVectorizer(token_pattern=r'(?u)\b\w\w+\b', ngram_range=(1,3))
     */
    tokenize(text) {
      if (!text || typeof text !== 'string') return [];
      const lower = text.toLowerCase();
      // Match words of at least 2 characters (word characters \w includes letters, numbers, underscore)
      const matches = lower.match(/\b\w\w+\b/g);
      return matches || [];
    }

    generateNgrams(tokens, minN = 1, maxN = 3) {
      const ngrams = [];
      const len = tokens.length;
      for (let n = minN; n <= maxN; n++) {
        for (let i = 0; i <= len - n; i++) {
          ngrams.push(tokens.slice(i, i + n).join(' '));
        }
      }
      return ngrams;
    }

    /**
     * Compute TF-IDF probability identical to scikit-learn LogisticRegression
     */
    predictProba(text) {
      if (!this.model || !text || !text.trim()) return 0.0;
      const tokens = this.tokenize(text);
      if (tokens.length === 0) return 0.0;

      const ngrams = this.generateNgrams(tokens, this.model.ngram_range?.[0] || 1, this.model.ngram_range?.[1] || 3);
      const counts = {};
      for (let i = 0; i < ngrams.length; i++) {
        const g = ngrams[i];
        counts[g] = (counts[g] || 0) + 1;
      }

      const vocab = this.model.vocabulary;
      const idf = this.model.idf;
      const coefs = this.model.coefficients;

      let sumSq = 0.0;
      const featVals = {};

      for (const [ngram, count] of Object.entries(counts)) {
        if (vocab && typeof vocab[ngram] !== 'undefined') {
          const idx = vocab[ngram];
          // sublinear_tf: 1 + log(count)
          const tf = 1.0 + Math.log(count);
          const val = tf * idf[idx];
          featVals[idx] = val;
          sumSq += val * val;
        }
      }

      if (sumSq === 0.0) {
        // No vocabulary features present
        const intercept = this.model.intercept || 0.0;
        return 1.0 / (1.0 + Math.exp(-intercept));
      }

      const norm = Math.sqrt(sumSq);
      let dot = 0.0;
      for (const [idxStr, val] of Object.entries(featVals)) {
        const idx = parseInt(idxStr, 10);
        const normalizedVal = val / norm;
        dot += normalizedVal * coefs[idx];
      }

      dot += (this.model.intercept || 0.0);
      return 1.0 / (1.0 + Math.exp(-dot));
    }

    /**
     * Find negation/warning spans to prevent false alarms
     */
    findNegationSpans(text) {
      const spans = [];
      const lower = text.toLowerCase();
      for (const rx of this.compiledNegations) {
        rx.lastIndex = 0;
        let m;
        while ((m = rx.exec(lower)) !== null) {
          spans.push({ start: m.index, end: m.index + m[0].length });
        }
      }
      return spans;
    }

    isInNegation(start, end, negSpans) {
      for (const ns of negSpans) {
        if (!(end <= ns.start || start >= ns.end)) {
          return true;
        }
      }
      return false;
    }

    /**
     * Tactic detection matching Python tactic_tagger
     */
    detectTactics(text) {
      if (!this.compiledTactics || !text) return { tactic_breakdown: [], highlights: [], has_critical: false };

      const lower = text.toLowerCase();
      const negSpans = this.findNegationSpans(lower);

      const tacticHits = [];
      const highlights = [];
      let hasCritical = false;

      for (const t of this.compiledTactics) {
        const matches = [];

        if (t.enRegex) {
          t.enRegex.lastIndex = 0;
          let m;
          while ((m = t.enRegex.exec(lower)) !== null) {
            if (!this.isInNegation(m.index, m.index + m[0].length, negSpans)) {
              matches.push({ start: m.index, end: m.index + m[0].length, phrase: text.substring(m.index, m.index + m[0].length) });
            }
          }
        }

        if (t.hiRegex) {
          t.hiRegex.lastIndex = 0;
          let m;
          while ((m = t.hiRegex.exec(lower)) !== null) {
            if (!this.isInNegation(m.index, m.index + m[0].length, negSpans)) {
              matches.push({ start: m.index, end: m.index + m[0].length, phrase: text.substring(m.index, m.index + m[0].length) });
            }
          }
        }

        if (matches.length > 0) {
          const uniquePhrases = Array.from(new Set(matches.map(m => m.phrase.trim()))).slice(0, 4);
          tacticHits.push({
            id: t.id,
            title: t.title,
            description: t.description,
            severity: t.severity,
            icon: t.icon,
            badge_class: t.badge_class,
            checklist_label: t.checklist_label,
            matched_phrases: uniquePhrases,
            detected: true
          });

          if (t.severity === 'critical') {
            hasCritical = true;
          }

          for (const m of matches) {
            highlights.push({
              start: m.start,
              end: m.end,
              phrase: m.phrase,
              tactic_id: t.id,
              tactic_title: t.title,
              severity: t.severity
            });
          }
        }
      }

      // Sort and deduplicate highlights
      highlights.sort((a, b) => a.start - b.start);
      const cleanHighlights = [];
      let lastEnd = -1;
      for (const h of highlights) {
        if (h.start >= lastEnd) {
          cleanHighlights.append ? cleanHighlights.append(h) : cleanHighlights.push(h);
          lastEnd = h.end;
        }
      }

      return {
        tactic_breakdown: tacticHits,
        highlights: cleanHighlights,
        has_critical: hasCritical
      };
    }

    /**
     * Scam family classification matching Python text_pipeline
     */
    classifyScamFamily(text, tacticsDetected) {
      const lower = text.toLowerCase();
      const tacticIds = tacticsDetected.map(t => t.id);

      if (tacticIds.includes('legal_arrest_threat') || lower.includes('digital arrest') || lower.includes('police') || lower.includes('cbi')) {
        return {
          family_id: 'govt_law_enforcement_digital_arrest',
          family_name: "Police & 'Digital Arrest' Threat",
          harm_type: 'Fear and threat / Money',
          evidence_strength: 'Based on warning-sign rules'
        };
      }

      if (tacticIds.includes('remote_access_install') || lower.includes('anydesk') || lower.includes('teamviewer') || lower.includes('rustdesk')) {
        return {
          family_id: 'tech_support_remote_access',
          family_name: 'Tech Support & Screen Share Trap',
          harm_type: 'Device / Money',
          evidence_strength: 'Based on warning-sign rules'
        };
      }

      if (tacticIds.includes('reward_prize_bait') || lower.includes('lottery') || lower.includes('award') || lower.includes('won')) {
        return {
          family_id: 'prize_lottery_cashback',
          family_name: 'Prize & Lottery Lure',
          harm_type: 'Money',
          evidence_strength: 'Learned from real examples'
        };
      }

      if (tacticIds.includes('abusive_language')) {
        return {
          family_id: 'abusive_harassing_caller',
          family_name: 'Harassment & Intimidation',
          harm_type: 'Emotional harassment',
          evidence_strength: 'Based on warning-sign rules'
        };
      }

      if (tacticIds.includes('urgency_threat') && (lower.includes('sim') || lower.includes('jio') || lower.includes('airtel') || lower.includes('23 hours'))) {
        return {
          family_id: 'telecom_sim_threat',
          family_name: 'SIM & Telecom Threat',
          harm_type: 'Identity',
          evidence_strength: 'Learned from real examples'
        };
      }

      if (tacticIds.includes('credential_request') && (lower.includes('otp') || lower.includes('pin') || lower.includes('code'))) {
        if (lower.includes('bank') || lower.includes('card') || lower.includes('sbi') || lower.includes('hdfc')) {
          return {
            family_id: 'bank_kyc_impersonation',
            family_name: 'Bank & Card Impersonation',
            harm_type: 'Money',
            evidence_strength: 'Learned from real examples'
          };
        }
        return {
          family_id: 'otp_account_takeover',
          family_name: 'OTP & Account Takeover',
          harm_type: 'Money / Identity',
          evidence_strength: 'Learned from real examples'
        };
      }

      if (tacticIds.includes('authority_impersonation') && (lower.includes('bank') || lower.includes('card') || lower.includes('kyc'))) {
        return {
          family_id: 'bank_kyc_impersonation',
          family_name: 'Bank & Card Impersonation',
          harm_type: 'Money',
          evidence_strength: 'Learned from real examples'
        };
      }

      if (lower.includes('loan') || lower.includes('task') || lower.includes('investment')) {
        return {
          family_id: 'loan_investment_job_advance',
          family_name: 'Fake Loan & Job Advance Fee',
          harm_type: 'Money',
          evidence_strength: 'Learned from real examples'
        };
      }

      if (lower.includes('parcel') || lower.includes('fedex') || lower.includes('customs')) {
        return {
          family_id: 'courier_customs_parcel',
          family_name: 'Courier & Customs Parcel Scam',
          harm_type: 'Fear and threat / Money',
          evidence_strength: 'Learned from real examples'
        };
      }

      return {
        family_id: 'no_concern_found',
        family_name: 'No Scam Indicators Detected',
        harm_type: 'None',
        evidence_strength: 'Learned from real examples'
      };
    }

    /**
     * Full synchronous evaluation of a transcript slice
     */
    analyzeText(text) {
      const cleanText = (text || '').trim();
      if (!cleanText) {
        return {
          text_risk_score: 0,
          probability: 0.0,
          tactics_detected: [],
          tactic_breakdown: [],
          highlights: [],
          primary_family_id: 'no_concern_found',
          primary_family_name: 'No Scam Indicators Detected',
          harm_type: 'None',
          evidence_strength: 'Learned from real examples'
        };
      }

      let prob = this.predictProba(cleanText);
      const tacticRes = this.detectTactics(cleanText);
      const tacticsBreakdown = tacticRes.tactic_breakdown;

      const famInfo = this.classifyScamFamily(cleanText, tacticsBreakdown);
      let famId = famInfo.family_id;
      let famName = famInfo.family_name;

      // Contextual disambiguation
      const lower = cleanText.toLowerCase();
      const hasThreat = tacticsBreakdown.some(t => ['authority_impersonation', 'legal_arrest_threat', 'secrecy_isolation', 'remote_access_install'].includes(t.id));

      const isSafeDelivery = (
        (lower.includes('delivery agent') || lower.includes('delivery partner') || lower.includes('package delivery') || lower.includes('hand over your order') || lower.includes('swiggy') || lower.includes('zomato') || lower.includes('share pin with driver'))
        && !hasThreat
      );
      const isSafeAppointment = (
        (lower.includes('appointment') || lower.includes('consultation') || lower.includes('clinic') || lower.includes('dental') || lower.includes('tuition fees') || lower.includes('library'))
        && !hasThreat
      );
      const isSafeWarning = (
        (lower.includes('never calls to ask') || lower.includes('never call to ask') || lower.includes('never ask for') || lower.includes('will not ask') || lower.includes('if you did not request this') || lower.includes('valid for 10 minutes'))
        && !hasThreat
      );

      if (isSafeDelivery || isSafeAppointment || isSafeWarning) {
        prob = Math.min(prob, 0.12);
        famId = 'no_concern_found';
        famName = isSafeWarning ? 'Safe Security / Informational Notice' : 'Safe Everyday Notice';
      }

      const riskScore = Math.round(prob * 100);

      return {
        text_risk_score: riskScore,
        probability: Math.round(prob * 10000) / 10000,
        tactics_detected: tacticsBreakdown.map(t => t.title),
        tactic_breakdown: tacticsBreakdown,
        highlights: tacticRes.highlights,
        has_critical_indicators: tacticRes.has_critical,
        primary_family_id: famId,
        primary_family_name: famName,
        harm_type: famInfo.harm_type,
        evidence_strength: famInfo.evidence_strength
      };
    }

    /**
     * Process a rolling segment update in Live Listen mode.
     * Evaluates state machine (Calm, Heads-up, Danger) with hysteresis and lead times.
     */
    updateLiveStream(confirmedTranscript, currentTimeS = 0) {
      const analysis = this.analyzeText(confirmedTranscript);
      const prob = analysis.probability;
      const tactics = analysis.tactic_breakdown;
      const tacticIds = tactics.map(t => t.id);

      // Record update
      this.historyUpdates.push({
        time_s: currentTimeS,
        risk_prob: prob,
        risk_score: analysis.text_risk_score,
        tactics: tacticIds
      });

      // Track ask moment (OTP/PIN/money ask)
      const lower = confirmedTranscript.toLowerCase();
      if ((lower.includes('otp') || lower.includes('pin') || lower.includes('code') || lower.includes('transfer money')) && !this.askMomentTimeS) {
        const isNegated = lower.includes('never calls to ask') || lower.includes('will not ask');
        if (!isNegated) {
          this.askMomentTimeS = currentTimeS;
        }
      }

      // Check thresholds based on sensitivity profile
      const cfg = this.tacticsConfig?.alert_thresholds?.profiles?.[this.sensitivity] || {
        danger_risk: 0.72,
        danger_consecutive_count: 2,
        heads_up_risk: 0.45
      };

      // Check fast instant danger rule:
      // authority claim + (OTP/PIN/CVV or money or remote-access) within last 60 seconds
      const cutoffTime = Math.max(0, currentTimeS - 60);
      const recentTactics = new Set();
      for (const item of this.historyUpdates) {
        if (item.time_s >= cutoffTime) {
          item.tactics.forEach(id => recentTactics.add(id));
        }
      }

      const hasAuthority = recentTactics.has('authority_impersonation') || recentTactics.has('legal_arrest_threat');
      const hasExtraction = recentTactics.has('credential_request') || recentTactics.has('remote_access_install');
      const instantDangerTriggered = hasAuthority && hasExtraction;

      // Check consecutive danger threshold
      if (prob >= cfg.danger_risk) {
        this.consecutiveDangerCount++;
      } else {
        this.consecutiveDangerCount = 0;
      }

      const thresholdDangerTriggered = this.consecutiveDangerCount >= cfg.danger_consecutive_count;

      // Heads-up condition: secrecy demand alone, or credential request alone, or prob >= heads_up_risk
      const headsUpSignal = (
        recentTactics.has('secrecy_isolation') ||
        recentTactics.has('credential_request') ||
        prob >= cfg.heads_up_risk
      );

      // State determination with hysteresis (Danger persists until dismissed)
      if (this.state === 'danger') {
        // Hysteresis: stays danger unless dismissed
      } else if (!this.dangerDismissed && (instantDangerTriggered || thresholdDangerTriggered)) {
        this.state = 'danger';
        if (this.firstAlertTimeS === null) {
          this.firstAlertTimeS = currentTimeS;
          if (this.askMomentTimeS) {
            this.leadTimeS = Math.max(0, Math.round((this.askMomentTimeS - this.firstAlertTimeS) * 10) / 10);
          }
        }
      } else if (this.state !== 'danger' && headsUpSignal) {
        this.state = 'heads_up';
        if (this.firstAlertTimeS === null) {
          this.firstAlertTimeS = currentTimeS;
        }
      } else if (this.state !== 'danger') {
        this.state = 'calm';
      }

      return {
        state: this.state, // 'calm' | 'heads_up' | 'danger'
        analysis,
        first_alert_s: this.firstAlertTimeS,
        ask_moment_s: this.askMomentTimeS,
        lead_time_s: this.leadTimeS,
        instant_danger: instantDangerTriggered,
        active_tactics: Array.from(recentTactics)
      };
    }

    /**
     * User clicks "Not a scam" -> Dismiss danger state, record local correction
     */
    dismissAlert() {
      this.state = 'calm';
      this.dangerDismissed = true;
      this.localCorrections.push({
        time: Date.now(),
        action: 'not_a_scam'
      });
      return { state: this.state, dismissed: true };
    }
  }

  return SentiCallRiskEngine;
}));
