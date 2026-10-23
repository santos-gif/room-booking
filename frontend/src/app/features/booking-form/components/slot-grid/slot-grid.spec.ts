import { TestBed } from '@angular/core/testing';
import { AvailableSlot } from '../../types/booking-form';
import { SlotGrid } from './slot-grid';

const slot = (hour: string, available: boolean): AvailableSlot => ({
	start_time: `2030-01-08T${hour}:00:00+07:00`,
	end_time: `2030-01-08T${Number(hour) + 1}:00:00+07:00`,
	available,
});

function render(inputs: Record<string, unknown>) {
	const fixture = TestBed.createComponent(SlotGrid);
	for (const [name, value] of Object.entries(inputs)) {
		fixture.componentRef.setInput(name, value);
	}
	fixture.detectChanges();
	const buttons = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')];
	return { fixture, buttons };
}

describe('SlotGrid (a taken slot can never be booked)', () => {
	it('disables unavailable slots and labels each slot Free or Unavailable', () => {
		const { buttons } = render({ slots: [slot('09', true), slot('10', false)] });
		expect(buttons.map((b) => b.disabled)).toEqual([false, true]);
		expect(buttons[0].textContent).toContain('09:00 AM');
		expect(buttons[0].textContent).toContain('Free');
		expect(buttons[1].textContent).toContain('Unavailable');
	});

	it('emits the clicked slot, and nothing for a disabled one', () => {
		const free = slot('09', true);
		const { fixture, buttons } = render({ slots: [free, slot('10', false)] });
		const picked: AvailableSlot[] = [];
		fixture.componentInstance.pick.subscribe((value) => picked.push(value));
		buttons[0].click();
		buttons[1].click();
		expect(picked).toEqual([free]);
	});

	it('locks every slot while a booking is being submitted', () => {
		const { buttons } = render({ slots: [slot('09', true)], disabled: true });
		expect(buttons[0].disabled).toBe(true);
	});

	it('shows no slots at all while availability is loading', () => {
		const { fixture, buttons } = render({ slots: [slot('16', true)], loading: true });
		expect(buttons.length).toBe(0);
		expect(
			(fixture.nativeElement as HTMLElement).querySelector('.spinner'),
		).toBeTruthy();
	});

	it('strips the booking’s own time from the choices (picking it changes nothing), but labels it', () => {
		// Same instant in two spellings: the API mixes +07:00 and Z.
		const { fixture, buttons } = render({
			slots: [slot('09', true), slot('10', true)],
			current: '2030-01-08T02:00:00Z',
		});
		const outlined = [
			...(fixture.nativeElement as HTMLElement).querySelectorAll('.slot.current'),
		];
		expect(outlined.length).toBe(1);
		expect(buttons[0].disabled).toBe(true);
		expect(buttons[1].disabled).toBe(false);
		expect(buttons[0].textContent).toContain('Your booking');
		expect(buttons[1].textContent).toContain('Free');
	});

	it('marks the selected slot as pressed', () => {
		const chosen = slot('09', true);
		const { buttons } = render({ slots: [chosen, slot('11', true)], selected: chosen });
		expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual([
			'true',
			'false',
		]);
	});
});
