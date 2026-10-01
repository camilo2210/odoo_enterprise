<?xml version="1.0" encoding="utf-8"?>
<templates>
    <t t-name="room.RoomBookingView">
        <div class="row d-flex g-0 h-lg-100 bg-white">
            <div class="o_room_booking_main col-lg-8 col-xl-9 position-relative d-flex flex-column h-lg-100 overflow-lg-auto">
                <t t-if="this.state.scheduleBooking or this.state.bookingToEdit">
                    <RoomBookingForm bookings="this.state.bookings" createBooking.bind="this.scheduleBooking" cancel.bind="this.resetBookingForm" editBooking.bind="this.editBooking" bookingName="this.state.bookingName" bookingToEdit="this.state.bookingToEdit"/>
                </t>
                <div t-else="" class="d-flex flex-column flex-grow-1 justify-content-between gap-5 p-3 text-white fs-2"
                     t-attf-style="background-image: linear-gradient(#{this.bgColor}, #{this.bgColor}), url('#{this.manageRoomUrl}/background')">
                    <span class="position-absolute top-0 start-0 w-100 h-100 bg-gradient"/>
                    <div class="o_room_top position-relative text-end">
                        <RoomDisplayTime/>
                    </div>
                    <div class="position-relative d-flex flex-fill flex-column align-items-center justify-content-around gap-3 w-100">
                        <t t-if="!this.state.currentBooking">
                            <t t-if="this.state.scheduleBookingQuickCreate">
                                <h1 class="text-white">Booking Now</h1>
                                <div>
                                    <input t-if="!this.nextBooking || this.nextBooking.interval.start > this.now.plus({minutes: 15})" t-model.proxy.lazy.trim="this.state.bookingName" class="form-control bg-white fs-4" placeholder="Booking Name"/>
                                    <div class="d-flex justify-content-center gap-3 my-3">
                                        <button class="btn btn-dark btn-lg flex-grow-1 rounded-pill px-3 px-lg-5"
                                            t-if="!this.nextBooking || this.nextBooking.interval.start > this.now.plus({minutes: 15})"
                                            t-on-click="() => this.quickCreateBooking(15)">
                                            15 min
                                        </button>
                                        <div t-else="" class="d-flex flex-column align-items-center gap-2 p-3 fs-6">
                                            <i class="oi oi-2x" data-icon="warning"/>
                                            The next booking is starting soon.
                                        </div>
                                        <button class="btn btn-dark btn-lg flex-grow-1 rounded-pill px-3 px-lg-5"
                                            t-if="!this.nextBooking || this.nextBooking.interval.start > this.now.plus({minutes: 30})"
                                            t-on-click="() => this.quickCreateBooking(30)">
                                            30 min
                                        </button>
                                        <button class="btn btn-dark btn-lg flex-grow-1 rounded-pill px-3 px-lg-5"
                                            t-if="!this.nextBooking || this.nextBooking.interval.start > this.now.plus({minutes: 60})"
                                            t-on-click="() => this.quickCreateBooking(60)">
                                            1 hour
                                        </button>
                                    </div>
                                    <div t-if="!this.nextBooking" class="d-flex mt-3 w-100">
                                        <span class="flex-grow-1 align-self-center border"/>
                                        <span class="mx-3 fs-6 text-uppercase">Or</span>
                                        <span class="flex-grow-1 align-self-center border"/>
                                    </div>
                                </div>
                            </t>
                            <t t-else="">
                                <div class="d-flex flex-column align-items-center">
                                    <i class="oi oi-3x oi-filled" data-icon="check_circle"/>
                                    <h1 class="mb-0 text-uppercase fw-bold display-3 text-white">Available</h1>
                                </div>
                            </t>
                        </t>
                        <t t-else="">
                            <div class="d-flex flex-column align-items-center">
                                <i class="oi oi-3x" data-icon="event_busy"/>
                                <h1 class="mb-0 text-uppercase fw-bold display-3 text-white">Booked</h1>
                                <span t-out="this.state.currentBooking.name" class="fs-5 opacity-75"/>
                            </div>
                            <RoomBookingRemainingTime endTime="this.state.currentBooking.interval.end"/>
                        </t>
                        <div class="d-flex flex-column flex-xl-row gap-4">
                            <button t-if="this.state.currentBooking" class="btn btn-lg btn-dark d-flex justify-content-center align-items-center gap-3 rounded-pill py-lg-3 px-3 px-lg-5" t-on-click="this.endCurrentBooking">
                                End Booking
                                <i class="oi oi-filled" data-icon="cancel"/>
                            </button>
                            <button t-elif="!this.state.scheduleBookingQuickCreate" class="btn btn-dark btn-lg d-flex justify-content-center align-items-center gap-3 rounded-pill py-lg-3 px-3 px-lg-5" t-on-click="() => this.state.scheduleBookingQuickCreate = true">
                                Start now
                                <i class="oi" data-icon="rocket_launch"/>
                            </button>
                            <button class="btn btn-light btn-lg d-flex justify-content-center align-items-center gap-3 rounded-pill py-lg-3 px-3 px-lg-5" t-on-click="() => this.state.scheduleBooking = true">
                                Add a Booking
                                <i class="oi" data-icon="calendar_add_on"/>
                            </button>
                        </div>
                    </div>
                    <div class="o_room_bottom position-relative d-flex gap-3 w-100" t-if="this.state.scheduleBookingQuickCreate">
                        <button class="btn btn-lg flex-grow-1 bg-dark bg-opacity-25 text-white" t-on-click="this.resetBookingForm">
                            Discard
                        </button>
                    </div>
                </div>
            </div>
            <div class="o_room_sidebar col-lg-4 col-xl-3 position-relative border-start bg-100">
                <t t-call="room.RoomBookingSidebar"/>
            </div>
        </div>
    </t>

    <t t-name="room.RoomBookingSidebar">
        <div class="position-lg-absolute top-0 start-0 end-0 bottom-0 d-flex flex-column justify-content-between h-100 p-3">
            <!-- todo: check rtl -->
            <div class="my-2 border-bottom">
                <h4 t-out="this.props.name"/>
                <div class="mb-3 text-muted" t-if="this.props.description" t-out="this.roomDescription"/>
            </div>
            <div t-if="this.state.bookings.length === 0" class="d-flex justify-content-center flex-column flex-fill py-3 text-center">
                <h5>No Bookings Planned</h5>
                <span class="text-muted">This room is as free as a fish in a sea of endless possibilities</span>
            </div>
            <div t-else="" class="flex-fill pt-1 overflow-auto">
                <div class="list-group">
                    <t t-set="today" t-value="this.state.currentDate"/>
                    <t t-set="previous_date" t-value="this.state.currentDate"/>
                    <t t-foreach="this.state.bookings" t-as="booking" t-key="booking.id">
                        <!-- Booking ending the same day it started, at midnight, is not displayed as a multiple day booking -->
                        <t t-set="is_multiple_day" t-value="booking.interval.end > booking.interval.start.startOf('day').plus({ day: 1 })"/>
                        <t t-set="is_next_date" t-value="booking.interval.start.startOf('day') > previous_date"/>
                        <!-- Today section is shown even if there are no bookings for this day -->
                        <t t-if="booking_first">
                            <h6 t-if="!is_multiple_day" class="mt-3 text-capitalize" t-out="today.toRelativeCalendar()"/>
                            <span t-if="is_next_date" class="text-center text-muted">No Bookings for Today</span>
                        </t>
                        <!-- Add new section if it's a new date or a multiple day booking -->
                        <t t-if="is_next_date || is_multiple_day">
                            <h6 class="mt-3 mb-2">
                                <span t-if="booking.interval.start.startOf('day').equals(today)" class="text-capitalize" t-out="today.toRelativeCalendar()"/>
                                <span t-else="" t-out="booking.interval.start.toLocaleString(this.dateFormat)"/>
                                <t t-if="is_multiple_day">
                                    - <br/><span t-out="booking.interval.end.toLocaleString(this.dateFormat)"/>
                                </t>
                            </h6>
                            <t t-set="previous_date" t-value="booking.interval.start.startOf('day')"/>
                        </t>
                        <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-start cursor-pointer"
                            t-att-class="this.state.bookingToEdit?.id === booking.id ? 'active' : ''"
                            t-on-click="() => this.state.bookingToEdit = {...booking}">
                            <div class="text-break">
                                <div class="d-flex align-items-center">
                                    <span t-out="booking.interval.start.toLocaleString(this.timeFormat)"/>
                                    <i class="oi mx-1 smaller text-muted" data-icon="east"/>
                                    <span t-out="booking.interval.end.toLocaleString(this.timeFormat)"/>
                                </div>
                                <div class="smaller" t-out="booking.name"/>
                            </div>
                            <button class="btn btn-link btn-dark me-n3 mt-n2 p-3 lh-1 smaller" t-on-click.stop="() => this.deleteBooking(booking.id)">
                                <i class="oi oi-filled" data-icon="delete"/>
                            </button>
                        </div>
                    </t>
                </div>
            </div>
            <div t-if="this.state.showInstallPwaButton" class="d-flex justify-content-center bg-200 mx-n3 mb-n3 p-2">
                <button class="btn btn-primary" t-on-click="this.installPwa">Install Application</button>
                <button class="btn btn-link position-absolute end-0" t-on-click="() => this.state.showInstallPwaButton = false">
                    <i class="oi" data-icon="close_small"/>
                </button>
            </div>
        </div>
    </t>
</templates>
