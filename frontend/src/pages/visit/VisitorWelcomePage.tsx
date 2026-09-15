export function VisitorWelcomePage() {
  return (
    <div className="visitor-page">
      <header className="visitor-header">
        <div className="visitor-logo" aria-hidden="true">VMS</div>
        <p className="visitor-org">Visitor Check-In</p>
        <h1 className="visitor-title">Welcome to Visitor Check-In</h1>
      </header>

      <section className="visitor-card" aria-labelledby="visitor-welcome-heading">
        <h2 id="visitor-welcome-heading" className="visitor-card__heading">
          Visitor Registration
        </h2>
        <p className="visitor-card__text">
          Scan the reception QR code to begin your visit registration. This mobile experience
          is optimized for quick, touch-friendly check-in on your phone.
        </p>

        <div className="visitor-actions">
          <button type="button" className="visitor-btn visitor-btn--primary" disabled>
            Start Registration
          </button>
          <button type="button" className="visitor-btn visitor-btn--secondary" disabled>
            I Have an Invitation
          </button>
        </div>
      </section>

      <footer className="visitor-footer">
        Visitor Management System
      </footer>
    </div>
  );
}
