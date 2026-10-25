import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';

interface QuantumOnboardingModalProps {
  isOpen: boolean;
  userName: string;
  onComplete: () => void;
}

interface QuantumOption {
  id: string;
  label: string;
  text: string;
  correct: boolean;
  explanation: string;
}

const QUESTION_TEXT =
  'In quantum computing, what fundamental principle allows a qubit to exist in a linear combination of both |0⟩ and |1⟩ states simultaneously until measured?';

const OPTIONS: QuantumOption[] = [
  {
    id: 'superposition',
    label: 'A',
    text: 'Quantum Superposition',
    correct: true,
    explanation: 'Superposition allows |ψ⟩ = α|0⟩ + β|1⟩, enabling quantum parallelism across 2ⁿ basis states simultaneously.',
  },
  {
    id: 'teleportation',
    label: 'B',
    text: 'Quantum Teleportation',
    correct: false,
    explanation: 'Teleportation transfers an unknown state using shared entanglement and classical communication.',
  },
  {
    id: 'decoherence',
    label: 'C',
    text: 'Thermal Decoherence',
    correct: false,
    explanation: 'Decoherence causes a quantum system to lose its phase coherence due to environmental noise.',
  },
  {
    id: 'parallelism',
    label: 'D',
    text: 'Classical Parallelism',
    correct: false,
    explanation: 'Classical parallelism evaluates states independently, whereas quantum superposition interferes amplitudes.',
  },
];

export function QuantumOnboardingModal({ isOpen, userName, onComplete }: QuantumOnboardingModalProps) {
  // Phase 1: 'question' | Phase 2: 'bright-welcome' | Phase 3: 'fading-out'
  const [phase, setPhase] = useState<'question' | 'bright-welcome' | 'fading-out'>('question');
  const [typedQuestion, setTypedQuestion] = useState('');
  const [typedWelcome, setTypedWelcome] = useState('');
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isTypingQuestion, setIsTypingQuestion] = useState(true);
  const [blochAngle, setBlochAngle] = useState(0);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // 1. Slow Typewriter for Question Text
  useEffect(() => {
    if (!isOpen || phase !== 'question') return;
    setTypedQuestion('');
    setIsTypingQuestion(true);
    let index = 0;
    const interval = window.setInterval(() => {
      index++;
      setTypedQuestion(QUESTION_TEXT.slice(0, index));
      if (index >= QUESTION_TEXT.length) {
        window.clearInterval(interval);
        setIsTypingQuestion(false);
      }
    }, 28); // Slow smooth typewriter

    return () => window.clearInterval(interval);
  }, [isOpen, phase]);

  // 2. Slow Typewriter for Bold "Welcome to the World Of Qiskit & Quantum" in Brighter Theme Phase
  useEffect(() => {
    if (!isOpen || phase !== 'bright-welcome') return;
    setTypedWelcome('');
    const welcomeTarget = 'Welcome to the World Of Qiskit & Quantum';
    let index = 0;
    const interval = window.setInterval(() => {
      index++;
      setTypedWelcome(welcomeTarget.slice(0, index));
      if (index >= welcomeTarget.length) {
        window.clearInterval(interval);
        // Linger much longer, then transition out slowly
        window.setTimeout(() => {
          setPhase('fading-out');
          window.setTimeout(() => {
            onCompleteRef.current();
          }, 1800); // slower fade-out
        }, 3200); // longer linger before fading
      }
    }, 90); // slower, more deliberate typewriter

    return () => window.clearInterval(interval);
  }, [isOpen, phase]);

  // 3. Smooth Rotating Quantum Bloch Sphere Animation Loop
  useEffect(() => {
    if (!isOpen) return;
    let frameId: number;
    const animate = () => {
      setBlochAngle((prev) => (prev + 0.65) % 360);
      frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelect = (optionId: string) => {
    setSelectedOption(optionId);
  };

  const handleProceedToBrighterTheme = () => {
    setPhase('bright-welcome');
  };

  // Convert Bloch angles to 2D projection coordinates
  const rad = (blochAngle * Math.PI) / 180;
  const vecX = 60 + 38 * Math.cos(rad);
  const vecY = 60 - 32 * Math.sin(rad);

  return (
    <div
      className={`quantum-onboarding-overlay ${phase === 'bright-welcome' ? 'phase-bright-quantum' : ''} ${
        phase === 'fading-out' ? 'phase-fading-out' : ''
      }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-welcome-title"
    >
      {/* Background Animated Quantum Mesh Canvas */}
      <div className="quantum-mesh-ambient" aria-hidden="true" />
      <div className="quantum-nebula-lights" aria-hidden="true" />

      {phase === 'question' && (
        <div className="quantum-onboarding-card">
          {/* Header */}
          <div className="onboarding-header">
            <span className="onboarding-badge">
              <Icon name="spark" size={13} />
              <span>QUANTUM INITIATION</span>
            </span>
            <h1 id="onboarding-welcome-title" className="onboarding-name-title">
              Welcome, <span className="quantum-gradient-text">{userName || 'Explorer'}</span>
            </h1>
            <p className="onboarding-subtitle">
              Welcome to QORE Quantum Studio. Let&apos;s calibrate your quantum intuition before entering the workbench.
            </p>
          </div>

          {/* Interactive Quantum World Visualizer */}
          <div className="onboarding-visual-world">
            <div className="quantum-bloch-stage">
              <svg viewBox="0 0 120 120" className="quantum-bloch-svg" width="130" height="130">
                <defs>
                  <radialGradient id="sphereGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
                    <stop offset="70%" stopColor="#818cf8" stopOpacity="0.12" />
                    <stop offset="100%" stopColor="#030712" stopOpacity="0.8" />
                  </radialGradient>
                  <linearGradient id="vectorGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#00f0ff" />
                    <stop offset="100%" stopColor="#ec4899" />
                  </linearGradient>
                </defs>

                {/* Sphere sphere outline & shadow */}
                <circle cx="60" cy="60" r="46" fill="url(#sphereGlow)" stroke="#38bdf8" strokeWidth="1.2" opacity="0.85" />
                {/* Equator */}
                <ellipse cx="60" cy="60" rx="46" ry="14" fill="none" stroke="#60a5fa" strokeWidth="0.9" strokeDasharray="2 3" opacity="0.6" />
                {/* Meridian */}
                <ellipse cx="60" cy="60" rx="14" ry="46" fill="none" stroke="#818cf8" strokeWidth="0.9" strokeDasharray="2 3" opacity="0.6" />
                {/* Z-Axis */}
                <line x1="60" y1="10" x2="60" y2="110" stroke="#94a3b8" strokeWidth="1.1" strokeDasharray="3 3" opacity="0.7" />
                {/* Poles */}
                <text x="60" y="8" fill="#00f0ff" fontSize="9" textAnchor="middle" fontWeight="bold">|0⟩</text>
                <text x="60" y="119" fill="#f472b6" fontSize="9" textAnchor="middle" fontWeight="bold">|1⟩</text>

                {/* Rotating State Vector |ψ⟩ */}
                <line x1="60" y1="60" x2={vecX} y2={vecY} stroke="url(#vectorGrad)" strokeWidth="2.4" strokeLinecap="round" />
                <circle cx={vecX} cy={vecY} r="4" fill="#00f0ff" filter="drop-shadow(0 0 6px #00f0ff)" />
                <circle cx="60" cy="60" r="3" fill="#ffffff" />
                <text x={vecX + 6} y={vecY - 2} fill="#ffffff" fontSize="9" fontWeight="bold">|ψ⟩</text>
              </svg>

              <div className="quantum-state-formula">
                <span className="formula-tag">STATE SUPERPOSITION</span>
                <code>|ψ⟩ = α|0⟩ + β|1⟩</code>
                <small className="formula-sub">|α|² + |β|² = 1</small>
              </div>
            </div>
          </div>

          {/* Question Box with Slow Gradient Typewriter */}
          <div className="onboarding-question-box">
            <span className="question-kicker">CALIBRATION QUESTION</span>
            <h3 className="typewriter-question-text">
              {typedQuestion}
              {isTypingQuestion && <span className="typewriter-cursor">|</span>}
            </h3>
          </div>

          {/* Interactive Answer Cards */}
          <div className="onboarding-options-grid" role="radiogroup" aria-label="Quantum Question Answers">
            {OPTIONS.map((opt) => {
              const isSelected = selectedOption === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`onboarding-option-card ${isSelected ? 'selected' : ''} ${
                    isSelected && opt.correct ? 'is-correct' : ''
                  }`}
                  onClick={() => handleSelect(opt.id)}
                >
                  <div className="option-badge">{opt.label}</div>
                  <div className="option-content">
                    <span className="option-title">{opt.text}</span>
                    {isSelected && (
                      <p className="option-explanation">{opt.explanation}</p>
                    )}
                  </div>
                  {isSelected && opt.correct && (
                    <span className="option-check-icon">
                      <Icon name="check" size={14} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Action Footer */}
          <div className="onboarding-footer">
            <button
              type="button"
              className="clean-button primary onboarding-proceed-btn"
              disabled={!selectedOption}
              onClick={handleProceedToBrighterTheme}
            >
              <span>Initialize Quantum Experience</span>
              <Icon name="arrow" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Phase 2: Radiant Brighter Quantum Theme Transformation */}
      {phase === 'bright-welcome' && (
        <div className="bright-quantum-stage">
          <div className="bright-quantum-flare" />
          <div className="bright-quantum-ring ring-l1" />
          <div className="bright-quantum-ring ring-l2" />
          <div className="bright-quantum-ring ring-l3" />

          <div className="bright-quantum-content">
            <span className="bright-quantum-pretitle">SYNCHRONIZATION COMPLETE</span>
            <h1 className="bright-typewriter-hero">
              {typedWelcome}
              <span className="bright-cursor">|</span>
            </h1>
            <p className="bright-quantum-sublead">
              Expanding multi-qubit registers & preparing your quantum simulation workbench...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
