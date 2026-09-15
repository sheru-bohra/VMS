interface Step {
  id: number;
  label: string;
}

interface RegistrationStepperProps {
  steps: Step[];
  activeStep: number;
  completedSteps: number[];
  onStepClick: (stepId: number) => void;
}

export function RegistrationStepper({
  steps,
  activeStep,
  completedSteps,
  onStepClick,
}: RegistrationStepperProps) {
  return (
    <nav className="rv-stepper" aria-label="Registration progress">
      {steps.map((step, index) => {
        const completed = completedSteps.includes(step.id);
        const active = step.id === activeStep;
        return (
          <div key={step.id} className="rv-stepper__item">
            <button
              type="button"
              className={`rv-stepper__step ${active ? 'rv-stepper__step--active' : ''} ${completed ? 'rv-stepper__step--done' : ''}`}
              onClick={() => onStepClick(step.id)}
              aria-current={active ? 'step' : undefined}
            >
              <span className="rv-stepper__circle">
                {completed && !active ? (
                  <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                    <path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" strokeWidth="2" />
                  </svg>
                ) : (
                  step.id
                )}
              </span>
              <span className="rv-stepper__label">{step.label}</span>
            </button>
            {index < steps.length - 1 && (
              <span
                className={`rv-stepper__line ${completed ? 'rv-stepper__line--done' : ''}`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
