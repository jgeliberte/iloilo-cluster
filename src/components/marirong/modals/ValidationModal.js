import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button, Typography, TextField } from '@mui/material';
import React, { Fragment, useState, useEffect } from 'react';


function ValidationModal(props) {
    const { isOpen, trigger, setOpenModal, handleValidation, triggers, setTriggers } = props;

    const invalidAlert = () => {
        setOpenModal(false);
        handleValidation("Invalidated alert success!");
        let temp = triggers.filter(e => e.id !== trigger.id);
        let current_trigger = { ...trigger };
        current_trigger.validity_status = -1;
        temp.push(current_trigger);
        setTriggers(temp)

    }

    const validatingAlert = () => {
        setOpenModal(false);
        handleValidation("Validating alert success!");
    }

    const validAlert = () => {
        setOpenModal(false);
        handleValidation("Alert validation success!");
        let temp = triggers.filter(e => e.id !== trigger.id);
        let current_trigger = { ...trigger };
        current_trigger.validity_status = 1;
        temp.push(current_trigger);
        setTriggers(temp)

    }
    return (
        <Dialog
            fullWidth
            fullScreen={false}
            open={isOpen}
            aria-labelledby="form-dialog-title"

        >
            <DialogTitle id="form-dialog-title">Validate Alert</DialogTitle>
            <DialogContent>
                <Typography variant="body1">{trigger.trigger} - Alert level {trigger.alert_level}</Typography>
                <Typography variant="subtitle2">{trigger.tech_info}</Typography>
                <TextField id="standard-basic" label="Remarks" fullWidth style={{ marginTop: 10 }} />
            </DialogContent>
            <DialogActions>
                <Button onClick={validatingAlert}>
                    Validating
                </Button>
                <Button onClick={invalidAlert} color="secondary">
                    Invalid
                </Button>
                <Button onClick={() => validAlert("Alert validation success!")} color="primary">
                    Valid
                </Button>
            </DialogActions>
        </Dialog>
    )
}

export default ValidationModal;